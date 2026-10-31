# TrueFidelity demos

Example ECU applications and local topology files for [TrueFidelity](https://nebula-platform.dev).

| Example | What it demonstrates | Build |
| --- | --- | --- |
| [CAN gateway](can-gateway-iac/) | Two Python ECUs and a freestanding ARM C++ responder on two CAN networks | `./build.sh gateway` |
| [CAN ping-pong](can-pingpong-s32k3-zephyr/) | Two S32K344 Zephyr ECUs, an optional Python receiver, and automated tests | `./build.sh can` |
| [Ethernet ping-pong](ethernet-pingpong-s32g-linux/) | Two static ARM64 Linux applications exchanging UDP packets | `./build.sh ethernet` |

## Build an example

Clone the repository and select a demo:

```sh
git clone https://github.com/NebulaTechSolutions/tf-demo.git
cd tf-demo
./build.sh gateway
```

Run `./build.sh all` to build all three. Add `debug` as the second argument for
debug builds, for example `./build.sh can debug`. Each example also has its own
build script, described in its README.

Install the tools for the example you choose:

| Example | Tools |
| --- | --- |
| CAN gateway | Python 3, Clang with ARM target support, and LLVM LLD |
| CAN ping-pong | [tf CLI](https://nebula-platform.dev/docs/getting-started/install-cli) and its Zephyr build environment |
| Ethernet ping-pong | Bash, Make, and [Zig 0.15.2](https://ziglang.org/download/) |

On Ubuntu or Debian, install the gateway tools with
`sudo apt install python3 clang lld`. Download Zig separately from its website.
The gateway's Python-only ECUs need only Python 3. The CAN example's README
explains how to set up its toolchain. Building does not need a cloud login.

Generated files stay in each example's `build/` directory. The optional Ethernet
initramfs packaging step needs a base rootfs supplied by you. See its README.

## Run and debug

The [user manual](https://nebula-platform.dev/docs) covers installation, cloud
accounts, flashing firmware, VS Code, and bench gateways. Start with
[your first automated test](https://nebula-platform.dev/docs/testing/first-run).

The CAN examples include local topology files and test cases. Cloud execution
needs a TrueFidelity account and access to the runtime images named in those
files. The checked-in tests currently use development runtime images. Select
images accepted by your environment before running them.
