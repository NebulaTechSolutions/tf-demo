#!/usr/bin/env python3
"""Check the portable package, then optionally execute it through the local TF runtime."""

import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

import build


def declared_images():
    images = {"script": set(), "firmware": set()}
    topology = (build.ROOT / "topology.yaml").read_text()
    ecus = re.split(r"^  [A-Za-z]", topology.split("  ecus:\n", 1)[1], maxsplit=1, flags=re.MULTILINE)[0]
    for ecu in ecus.split("    - id:")[1:]:
        kind = re.search(r"^\s+ecu_type: (script|firmware)$", ecu, re.MULTILINE)
        image = re.search(r"^\s+image: (\S+)$", ecu, re.MULTILINE)
        if kind is None or image is None:
            raise ValueError("demo topology must declare each ECU type and pinned image")
        images[kind[1]].add(image[1])
    if any(len(values) != 1 for values in images.values()):
        raise ValueError("local verification needs one firmware image and one Python image")
    return next(iter(images["firmware"])), next(iter(images["script"]))


def execute(arguments, report_path=None):
    result = subprocess.run(arguments, text=True, capture_output=True)
    if result.returncode:
        details = report_path.read_text() if report_path and report_path.is_file() else ""
        raise RuntimeError(f"{arguments[0]} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}\n{details}")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tf", default="tf")
    parser.add_argument("--runner", type=Path, help="cloud target/debug/examples/run-pingpong executable")
    parser.add_argument("--sdk-source", type=Path, help="cloud/sdk/testing/src for local execution")
    parser.add_argument("--ecusim", type=Path, help="ECUSim ARM executable with the private ECU-time adapters")
    parser.add_argument("--ecu-image", help="override the local profile's firmware image identity")
    parser.add_argument("--python-image", help="override the local profile's Python image identity")
    args = parser.parse_args()
    runtime = (args.runner, args.sdk_source, args.ecusim)
    if any(runtime) and not all(runtime):
        parser.error("provide --runner, --sdk-source and --ecusim together")
    tf = shutil.which(args.tf)
    if tf is None:
        parser.error("tf executable not found")
    root = build.ROOT
    build.build(root / "build")
    assert (root / "build/ecus.zip").read_bytes() == build.archive(), "ECU archive is not reproducible"
    elf = (root / "build/cpp-responder.elf").read_bytes()
    assert elf[:7] == b"\x7fELF\x01\x01\x01", "expected a little-endian ELF32 binary"
    assert struct.unpack_from("<HH", elf, 16) == (2, 40), "expected an ARM executable"
    with tempfile.TemporaryDirectory(prefix="tf-iac-rebuild-") as temporary:
        build.build(Path(temporary), "cpp-responder")
        assert (Path(temporary) / "cpp-responder.elf").read_bytes() == elf, "firmware is not reproducible"
    discovered = execute([tf, "test", "discover", "--root", str(root), "--json"])
    assert len(discovered["definitions"]) == 4, discovered
    for name in ("echo", "reject", "cpp"):
        report = execute([tf, "test", "validate", "-f", str(root / "tests" / f"{name}.yaml"),
                          "--topology", str(root / "topology.yaml"), "--json"])
        assert report["valid"] and not report["execution_ready"], report
    report = execute([tf, "test", "validate", "-f", str(root / "tests/nightly.yaml"), "--json"])
    assert report["valid"] and len(report["cases"]) == 3, report
    print("PASS: reproducible Python archive and ARM C++ ELF, 3 test cases, 1 suite, offline validation")
    if args.runner:
        ecu_image, python_image = declared_images()
        with tempfile.TemporaryDirectory(prefix="tf-iac-demo-check-") as temporary:
            output = Path(temporary) / "results"
            result = execute([str(args.runner.resolve()), str(args.ecusim.resolve()), sys.executable,
                              str(args.sdk_source.resolve()), str(root), "tests/nightly.yaml",
                              str(output), "30", "--ecu-image", args.ecu_image or ecu_image,
                              "--python-image", args.python_image or python_image], report_path=output / "result.json")
            assert result["passed"] and result["cleanup"]["status"] == "complete", result
            assert result["summary"]["cases"]["passed"] == 3, result
            assert result["summary"]["checks"]["passed"] == 11, result
            print(f"PASS: real C++ firmware and Python ECUs, 3 cases, 11 checks, cleanup complete ({result['wall_seconds']:.3f}s)")


if __name__ == "__main__":
    main()
