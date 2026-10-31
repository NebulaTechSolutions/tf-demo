#!/usr/bin/env python3
"""Freeze real firmware, build Python metadata, and validate a portable test package."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
RUNTIME_DIGEST = "785dc2ac82f9646a68c0a0fce320d969a66ab61cf1e9b1b3115fd0f7a0f831be"
ECU_IMAGE = "harbor.nebula-platform.dev/truefidelity/test-runtime-ecu@sha256:" + RUNTIME_DIGEST
PYTHON_IMAGE = "harbor.nebula-platform.dev/truefidelity/test-runtime-python@sha256:" + RUNTIME_DIGEST


def pinned_image(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:/_-]*@sha256:[a-f0-9]{64}", value):
        raise argparse.ArgumentTypeError("use a runtime image pinned by SHA-256")
    return value


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    return path


def firmware(path):
    regular(path)
    with path.open("rb") as source:
        header = source.read(20)
    if len(header) < 20 or header[:7] != b"\x7fELF\x01\x01\x01" or header[18:20] != b"\x28\x00":
        raise ValueError(f"expected a little-endian 32-bit ARM ELF: {path}")
    return path


def execute(command, **options):
    return subprocess.run(command, check=True, text=True, capture_output=True, **options).stdout


def project_metadata(value, project):
    kind = re.search(r"^kind: (Topology|TestSuite)$", value, re.MULTILINE)
    if kind is None:
        return value
    section = "metadata" if kind[1] == "Topology" else "spec"
    lines = value.splitlines(keepends=True)
    start = lines.index(section + ":\n") + 1
    end = next((index for index in range(start, len(lines))
                if lines[index].strip() and not lines[index][0].isspace()), len(lines))
    line = "  project: " + json.dumps(project) + "\n"
    previous = next((index for index in range(start, end)
                     if lines[index].startswith("  project:")), None)
    if previous is None:
        lines.insert(start, line)
    else:
        lines[previous] = line
    return "".join(lines)


def portable_report(report, root):
    report["files"] = {str(Path(name).relative_to(root)): facts
                       for name, facts in report["files"].items()}
    for case in report["cases"]:
        for field in ("test", "topology"):
            case[field] = str(Path(case[field]).relative_to(root))
    return report


def prepare(args, source_root=HERE):
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"output exists; choose a new package directory: {output}")
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise ValueError("output parent must exist and contain no symlink or '..' components")
    sender, receiver = firmware(args.sender), firmware(args.receiver)
    tf = shutil.which(args.tf)
    if tf is None:
        raise ValueError(f"tf executable not found: {args.tf}")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if args.sdk_source:
        environment["PYTHONPATH"] = str(args.sdk_source.resolve(strict=True))
    execute([sys.executable, "-c", "import truefidelity.testing"], env=environment)
    output.mkdir(mode=0o700)
    artifacts = output / "artifacts"
    artifacts.mkdir()
    for name, source in (("sender", sender), ("receiver", receiver)):
        shutil.copyfile(source, artifacts / f"{name}.elf")
    shutil.copyfile(regular(DEMO / "pingpong.dbc"), output / "pingpong.dbc")
    for source in sorted(source_root.glob("*.yaml")):
        value = regular(source).read_text()
        value = value.replace(ECU_IMAGE, args.ecu_image).replace(PYTHON_IMAGE, args.python_image)
        value = value.replace("registry.example/ecu@sha256:" + "a" * 64, args.ecu_image)
        value = value.replace("registry.example/python@sha256:" + "b" * 64, args.python_image)
        if args.project:
            value = project_metadata(value, args.project)
        (output / source.name).write_text(value)
    sources = output / "sources"
    sources.mkdir()
    for name in ("checks.py", "receiver.py"):
        shutil.copyfile(regular(source_root / "python" / name), sources / name)
    execute([sys.executable, "-m", "truefidelity.testing", "bundle", "--root", str(sources),
             "--export", "checks.environment", "--export", "checks.verify_environment",
             "--include", "receiver.py", "--output", str(artifacts / "python.tar.gz")], env=environment)
    reports = {}
    for name in ("receiver-suite.yaml", "nightly.yaml", "mixed-suite.yaml"):
        report = json.loads(execute([tf, "--json", "test", "validate", "-f", str(output / name)]))
        if report.get("valid") is not True or report.get("execution_ready") is not False:
            raise ValueError(f"unexpected offline validation result: {name}")
        reports[name] = portable_report(report, output)
    hashes = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(output.rglob("*")) if path.is_file()}
    receipt = {
        "execution_ready": False,
        "note": "Offline validation is not a runtime or deployment result.",
        "firmware_sources": {"sender": str(sender.resolve()), "receiver": str(receiver.resolve())},
        "tf_version": execute([tf, "--version"]).strip(),
        "sha256": hashes,
        "validation": reports,
    }
    with (output / "preparation.json").open("x") as destination:
        json.dump(receipt, destination, indent=2, sort_keys=True)
        destination.write("\n")
    return {"prepared": str(output), "valid": True, "execution_ready": False,
            "suites": list(reports)}


def prepare_in_place(args):
    root = args.output.absolute()
    if not root.is_dir() or root.resolve() != root:
        raise ValueError("in-place output must be an existing directory without symlinks or '..'")
    with tempfile.TemporaryDirectory(prefix="pingpong-prepare-") as directory:
        staged = argparse.Namespace(**vars(args))
        staged.output = Path(directory) / "package"
        result = prepare(staged, root)
        files = [*sorted((staged.output / "artifacts").iterdir()),
                 staged.output / "pingpong.dbc", *sorted(staged.output.glob("*.yaml"))]
        receipt_path = staged.output / "preparation.json"
        receipt = json.loads(receipt_path.read_text())
        installed = {str(source.relative_to(staged.output)) for source in files}
        receipt["sha256"] = {name: digest for name, digest in receipt["sha256"].items()
                             if name in installed}
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        files.append(receipt_path)
        for source in files:
            destination = root / source.relative_to(staged.output)
            if destination.is_symlink() or destination.parent.is_symlink():
                raise ValueError(f"refusing generated output through a symlink: {destination}")
        for source in files:
            destination = root / source.relative_to(staged.output)
            destination.parent.mkdir(exist_ok=True)
            if destination.exists() and destination.read_bytes() == source.read_bytes():
                continue
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as pending:
                temporary = Path(pending.name)
                try:
                    with source.open("rb") as content:
                        shutil.copyfileobj(content, pending)
                    pending.flush()
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
        result["prepared"] = str(root)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new package directory")
    parser.add_argument("--in-place", action="store_true",
                        help="prepare artifacts beside authored tests in the output directory")
    parser.add_argument("--sender", type=Path, required=True, help="built Zephyr sender ELF")
    parser.add_argument("--receiver", type=Path, required=True, help="built Zephyr receiver ELF")
    parser.add_argument("--ecu-image", type=pinned_image, default=ECU_IMAGE)
    parser.add_argument("--python-image", type=pinned_image, default=PYTHON_IMAGE)
    parser.add_argument("--project", help="optional exported project metadata; does not select execution ownership")
    parser.add_argument("--tf", default="tf")
    parser.add_argument("--sdk-source", type=Path, help="cloud/sdk/testing/src, if the SDK is not installed")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare_in_place(args) if args.in_place else prepare(args)))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = (error.stderr or error.stdout or str(error)) if isinstance(error, subprocess.CalledProcessError) else str(error)
        parser.exit(1, f"Preparation failed: {detail}\nNo successful preparation.json receipt was written.\n")


if __name__ == "__main__":
    main()
