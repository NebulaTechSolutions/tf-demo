#!/usr/bin/env python3
"""Verify Python behavior and reproducible package preparation without a cloud connection."""

import argparse
import asyncio
import importlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import prepare


class ReceiverTests(unittest.TestCase):
    def test_all_sequence_counters_keep_the_pong_header(self):
        for counter in range(256):
            frame = CanFrame(0x123, b"PING" + bytes([counter, 50, 10, 0]))
            reply = receiver.reply_to(frame, 15_000_000, 0)
            self.assertEqual(reply, CanFrame(0x125, b"PONG" + bytes([counter, 0, 5, 0])))

    def test_wrong_header_identifier_length_and_extended_frame_are_ignored(self):
        frames = [CanFrame(0x122, b"PING\x00\x32\x00\x00"),
                  CanFrame(0x123, b"NOPE\x00\x32\x00\x00"),
                  CanFrame(0x123, b"PING\x00\x32\x00"),
                  CanFrame(0x123, b"PING\x00\x32\x00\x00", extended=True)]
        for frame in frames:
            with self.subTest(frame=frame):
                self.assertIsNone(receiver.reply_to(frame, 0, 0))

    def test_timestamp_offset_and_wrap_match_firmware_clamping(self):
        frame = CanFrame(0x123, b"PING\x00\x32\xff\xff")
        self.assertEqual(receiver.reply_to(frame, 65_540_000_000, 0).data[-2:], b"\x00\x00")
        frame = CanFrame(0x123, b"PING\x00\x32\x0a\x00")
        self.assertEqual(receiver.reply_to(frame, 115_000_000, 100_000_000).data[-2:], b"\x05\x00")

    def test_entrypoint_uses_ecu_clock_and_can0(self):
        class EndOfInput(Exception):
            pass

        class Ecu:
            def __init__(self):
                self.now = 100_000_000
                self.pending = [CanFrame(0x123, b"PING\x09\x32\x0a\x00")]
                self.sent = []

            def can(self, interface):
                self.interface = interface
                return self

            def now_ns(self):
                return self.now

            async def receive(self):
                if not self.pending:
                    raise EndOfInput
                self.now += 15_000_000
                return ReceivedFrame(self.pending.pop(0), self.now)

            async def send(self, frame):
                self.sent.append(frame)

        ecu = Ecu()
        with self.assertRaises(EndOfInput):
            asyncio.run(receiver.main(ecu))
        self.assertEqual(ecu.interface, "can0")
        self.assertEqual(ecu.sent, [CanFrame(0x125, b"PONG\x09\x00\x05\x00")])

    def test_decorators_publish_typed_inputs_and_environment_scope(self):
        check = checks.verify_environment.__tf_definition__.metadata()
        fixture = checks.environment.__tf_definition__.metadata()
        self.assertEqual(check["inputs"]["required"], ["minimum_ns", "maximum_ns"])
        self.assertEqual(check["inputs"]["properties"]["minimum_ns"]["type"], "integer")
        self.assertEqual(fixture["scope"], "environment")


class PreparationTests(unittest.TestCase):
    def assert_receipt_matches(self, root):
        receipt = json.loads((root / "preparation.json").read_text())
        self.assertNotIn("pingpong-prepare-", json.dumps(receipt))
        for name, digest in receipt["sha256"].items():
            path = root / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)
        for report in receipt["validation"].values():
            for name, facts in report["files"].items():
                self.assertFalse(Path(name).is_absolute(), name)
                self.assertTrue((root / name).is_file(), name)
                self.assertEqual(facts["sha256"], receipt["sha256"][name], name)
            for case in report["cases"]:
                for field in ("test", "topology"):
                    self.assertFalse(Path(case[field]).is_absolute(), case[field])
                    self.assertTrue((root / case[field]).is_file(), case[field])
        return receipt

    def command(self, output):
        return [sys.executable, str(prepare.HERE / "prepare.py"), "--sender", str(OPTIONS.sender),
                "--receiver", str(OPTIONS.receiver), "--project", "offline-verification",
                "--ecu-image", prepare.ECU_IMAGE, "--python-image", prepare.PYTHON_IMAGE,
                "--tf", OPTIONS.tf, "--output", str(output),
                *(["--sdk-source", str(OPTIONS.sdk_source)] if OPTIONS.sdk_source else [])]

    def test_actual_cli_validates_all_suites_and_packages_are_reproducible(self):
        with tempfile.TemporaryDirectory(prefix="pingpong-packages-") as directory:
            root = Path(directory)
            receipts = []
            for name in ("first", "second"):
                completed = subprocess.run(self.command(root / name), check=True, text=True, capture_output=True)
                self.assertTrue(json.loads(completed.stdout)["valid"])
                receipt = json.loads((root / name / "preparation.json").read_text())
                self.assert_receipt_matches(root / name)
                self.assertIn('  project: "offline-verification"', (root / name / "nightly.yaml").read_text())
                self.assertIn('  project: "offline-verification"', (root / name / "topology-firmware.yaml").read_text())
                self.assertFalse(receipt["execution_ready"])
                self.assertEqual(len(receipt["validation"]["nightly.yaml"]["cases"]), 4)
                receipts.append(receipt)
            self.assertEqual(receipts[0], receipts[1])
            rejected = subprocess.run(self.command(root / "first"), text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("output exists", rejected.stderr)
            self.assertEqual(json.loads((root / "first/preparation.json").read_text()), receipts[0])

    def test_mutable_image_tags_are_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            prepare.pinned_image("registry.example/ecu:latest")

    def test_in_place_preparation_makes_authored_suites_runnable(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix="pingpong-source-") as directory:
            root = Path(directory)
            for source in prepare.HERE.glob("*.yaml"):
                shutil.copyfile(source, root / source.name)
            shutil.copytree(prepare.HERE / "python", root / "python")
            before = (root / "nightly.yaml").read_bytes()
            command = self.command(root)
            command.remove("--project")
            command.remove("offline-verification")
            command.append("--in-place")
            subprocess.run(command, check=True, text=True, capture_output=True)
            self.assertEqual((root / "nightly.yaml").read_bytes(), before)
            self.assertEqual((root / "artifacts/sender.elf").read_bytes(), OPTIONS.sender.read_bytes())
            first_receipt = self.assert_receipt_matches(root)
            validated = subprocess.run([OPTIONS.tf, "--json", "test", "validate", "-f",
                                        str(root / "nightly.yaml")], check=True, text=True, capture_output=True)
            self.assertTrue(json.loads(validated.stdout)["valid"])
            subprocess.run(command, check=True, text=True, capture_output=True)
            self.assertEqual((root / "nightly.yaml").read_bytes(), before)
            self.assertEqual(self.assert_receipt_matches(root), first_receipt)

    def test_in_place_symlink_rejection_does_not_publish_other_files(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix="pingpong-symlink-") as directory:
            root = Path(directory) / "tests"
            root.mkdir()
            for source in prepare.HERE.glob("*.yaml"):
                shutil.copyfile(source, root / source.name)
            shutil.copytree(prepare.HERE / "python", root / "python")
            untouched = Path(directory) / "untouched.json"
            untouched.write_text("sentinel")
            (root / "preparation.json").symlink_to(untouched)
            before = {path.name: path.read_bytes() for path in root.glob("*.yaml")}
            command = self.command(root) + ["--in-place"]
            rejected = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("symlink", rejected.stderr)
            self.assertFalse((root / "artifacts").exists())
            self.assertFalse((root / "pingpong.dbc").exists())
            self.assertEqual(untouched.read_text(), "sentinel")
            self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.yaml")}, before)

    def test_missing_firmware_is_rejected_before_creating_package(self):
        with tempfile.TemporaryDirectory(prefix="pingpong-missing-") as directory:
            output = Path(directory) / "package"
            command = self.command(output)
            command[command.index("--sender") + 1] = str(Path(directory) / "missing.elf")
            rejected = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(output.exists())

    def test_non_arm_elf_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pingpong-elf-") as directory:
            bad = Path(directory) / "bad.elf"
            with bad.open("xb") as destination:
                destination.write(b"not an ELF firmware image")
            with self.assertRaises(ValueError):
                prepare.firmware(bad)
            link = Path(directory) / "link.elf"
            link.symlink_to(OPTIONS.receiver.resolve())
            with self.assertRaises(ValueError):
                prepare.firmware(link)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tf", default="tf")
    parser.add_argument("--sdk-source", type=Path)
    parser.add_argument("--sender", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    OPTIONS = parser.parse_args()
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    if OPTIONS.sdk_source:
        sys.path.insert(0, str(OPTIONS.sdk_source.resolve()))
    sys.path.insert(0, str(prepare.HERE / "python"))
    from truefidelity.testing.ecu import CanFrame
    from truefidelity.testing.ecu_can import ReceivedFrame
    receiver = importlib.import_module("receiver")
    checks = importlib.import_module("checks")
    unittest.main(argv=[sys.argv[0]], verbosity=2)
