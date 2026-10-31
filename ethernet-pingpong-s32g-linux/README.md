# Ethernet ping-pong on S32G Linux

Two AArch64 Linux applications exchange `PING` and `PONG` UDP packets on port
5000. They run on Linux ECUs in ECUSim or on a compatible Linux machine.

## Build the applications

Install Bash, Make, and [Zig 0.15.2](https://ziglang.org/download/). Zig includes
the ARM64 cross-compiler and musl C library used here.

```sh
./build.sh release
./build.sh debug
```

You can also run `make release` or `make debug`. Set `ZIG=/path/to/zig` if Zig is
not on your PATH.

The script writes static AArch64 Linux binaries:

- `build/release/eth_sender` and `build/release/eth_receiver`
- `build/debug/eth_sender` and `build/debug/eth_receiver`

Debug builds use `-g -O0`; release builds use `-O2`. Run `make clean` to remove
the generated binaries.

## Configure the network

| ECU | Address | Port |
| --- | --- | --- |
| Sender | `192.168.100.1/24` | UDP 5000 |
| Receiver | `192.168.100.2/24` | UDP 5000 |

Connect the Linux ECUs to the same Ethernet network. Start `eth_receiver` on the
receiver, then `eth_sender` on the sender. The sender prints round-trip results.
The addresses and port are defined in the source files.

## Package an existing initramfs

For a local ECUSim guest, supply a compatible base initramfs containing its
Linux startup files. This repository does not include a guest kernel or rootfs.
The packaging command needs Linux with GNU cpio, coreutils, and gzip.

```sh
./package-rootfs.sh /path/to/base-rootfs.cpio.gz release
```

This creates `test-rootfs.cpio.gz` with both applications under `/opt/demo` and
links at `/app/sender` and `/app/receiver`. Use it with your matching guest kernel.
Packaging does not configure the guest network or start either application.

See the [TrueFidelity manual](https://nebula-platform.dev/docs) for cloud setup
and debugging.
