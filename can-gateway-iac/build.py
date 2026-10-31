#!/usr/bin/env python3
"""Build the Python ECU archive and freestanding ARM C++ firmware."""

import argparse
import io
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent


def archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name in ("gateway.py", "receiver.py"):
            source = ROOT / "ecus" / name
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"expected a regular ECU source file: {source}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            bundle.writestr(info, source.read_bytes())
    return output.getvalue()


def linker_path(explicit):
    if explicit:
        return explicit
    installed = shutil.which("ld.lld")
    if installed:
        return installed
    if shutil.which("rustc"):
        libdir = subprocess.check_output(["rustc", "--print", "target-libdir"], text=True).strip()
        bundled = Path(libdir).parent / "bin/gcc-ld/ld.lld"
        if bundled.is_file():
            return str(bundled)
    raise FileNotFoundError("Install LLVM LLD or pass --linker /path/to/ld.lld")


def firmware(directory, compiler, linker, profile):
    source = ROOT / "ecus/cpp-responder"
    flags = [compiler, "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb", "-mfloat-abi=soft"]
    subprocess.run([*flags, "-std=c++17", "-g", "-Os" if profile == "release" else "-Og", "-ffreestanding", "-fno-exceptions", "-fno-rtti",
                    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-fno-stack-protector",
                    "-Wall", "-Wextra", "-Werror", "-c", str(source / "main.cpp"),
                    "-o", str(directory / "main.o")], check=True)
    subprocess.run([*flags, "-c", str(source / "startup.S"), "-o", str(directory / "startup.o")], check=True)
    subprocess.run([linker, "-T", str(source / "linker.ld"), "--build-id=none",
                    str(directory / "startup.o"), str(directory / "main.o"),
                    "-o", str(directory / "cpp-responder.elf")], check=True)


def build(directory, ecu=None, compiler="clang++", linker=None, profile="release"):
    if directory.is_symlink():
        raise ValueError("build directory must not be a symlink")
    directory.mkdir(exist_ok=True)
    outputs = (["cpp-responder.elf"] if ecu == "cpp-responder" else
               ["ecus.zip"] if ecu else ["ecus.zip", "cpp-responder.elf"])
    for name in outputs:
        if (directory / name).is_symlink():
            raise ValueError(f"build/{name} must not be a symlink")
    # Build privately first so a compiler error leaves the previous artifacts intact.
    with tempfile.TemporaryDirectory(prefix="tf-iac-build-") as temporary:
        staged = Path(temporary)
        if "cpp-responder.elf" in outputs:
            firmware(staged, compiler, linker_path(linker), profile)
        if "ecus.zip" in outputs:
            (staged / "ecus.zip").write_bytes(archive())
        for name in outputs:
            destination = directory / name
            destination.write_bytes((staged / name).read_bytes())
            print(f"Built {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang++", help="Clang C++ compiler with ARM target support")
    parser.add_argument("--linker", help="LLVM ld.lld (default: PATH or Rust's bundled linker)")
    parser.add_argument("--ecu", choices=["gateway", "receiver", "cpp-responder"],
                        help="Build one ECU artifact; Python ECUs share ecus.zip")
    parser.add_argument("--profile", choices=["release", "debug"], default="release")
    args = parser.parse_args()
    build(ROOT / "build", args.ecu, args.clang, args.linker, args.profile)


if __name__ == "__main__":
    main()
