#!/usr/bin/env python3
"""Run the real ping-pong suites locally through the production test runner."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import prepare


SUITES = ("receiver-suite.yaml", "nightly.yaml", "mixed-suite.yaml")


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_suite(args, package, suite):
    name = Path(suite).stem
    output = args.output / name
    command = [str(args.runner.resolve()), str(args.qemu.resolve()), sys.executable,
               str(args.sdk_source.resolve()), str(package), suite, str(output), str(args.wall_seconds),
               "--ecu-image", args.ecu_image, "--python-image", args.python_image]
    started = time.monotonic()
    timed_out = False
    with (args.output / f"{name}.stdout.log").open("x") as stdout, \
            (args.output / f"{name}.stderr.log").open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            process.wait(timeout=args.wall_seconds + 20)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_group(process)
        except BaseException:
            stop_group(process)
            raise
    receipt = output / "qualification.json"
    qualification = json.loads(receipt.read_text()) if receipt.is_file() else None
    passed = not timed_out and process.returncode == 0 and qualification is not None and qualification["passed"] is True
    result = {"suite": suite, "passed": passed, "returncode": process.returncode,
              "external_watchdog_expired": timed_out, "wall_seconds": time.monotonic() - started,
              "qualification": qualification}
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True,
                        help="cloud/target/debug/examples/run-pingpong, built before this command")
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--sdk-source", type=Path, required=True, help="cloud/sdk/testing/src")
    parser.add_argument("--sender", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--tf", default="tf")
    parser.add_argument("--ecu-image", type=prepare.pinned_image, default=prepare.ECU_IMAGE)
    parser.add_argument("--python-image", type=prepare.pinned_image, default=prepare.PYTHON_IMAGE)
    parser.add_argument("--output", type=Path, required=True, help="new directory for inputs and canonical reports")
    parser.add_argument("--wall-seconds", type=int, default=30, help="runner budget per suite, default 30")
    parser.add_argument("--suite", choices=SUITES, action="append", help="run selected suite; default all three")
    args = parser.parse_args()
    if not 1 <= args.wall_seconds <= 600:
        parser.error("--wall-seconds must be in 1..600")
    if args.suite and len(args.suite) != len(set(args.suite)):
        parser.error("select each suite at most once")
    for executable in (args.runner, args.qemu):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser.error(f"executable not found: {executable}")
    args.output = args.output.absolute()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must name a new directory")
    if not args.output.parent.is_dir() or args.output.parent.resolve() != args.output.parent:
        parser.error("output parent must exist without symlink or '..' components")
    args.output.mkdir(mode=0o700)
    package = args.output / "package"
    preparation = [sys.executable, str(prepare.HERE / "prepare.py"), "--sender", str(args.sender),
                   "--receiver", str(args.receiver), "--project", "local-qualification",
                   "--ecu-image", args.ecu_image, "--python-image", args.python_image,
                   "--tf", args.tf, "--sdk-source", str(args.sdk_source), "--output", str(package)]
    subprocess.run(preparation, check=True)
    results = [run_suite(args, package, suite) for suite in (args.suite or SUITES)]
    summary = {"passed": all(result["passed"] for result in results),
               "scope": "actual local production-runner suites; no cloud deployment or image pull",
               "local_profile_images": {"ecu": args.ecu_image, "python": args.python_image},
               "results": results}
    with (args.output / "qualification.json").open("x") as destination:
        json.dump(summary, destination, indent=2)
        destination.write("\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Suite qualification failed: {error}", file=sys.stderr)
        sys.exit(2)
