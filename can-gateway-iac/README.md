# CAN gateway local project

A complete topology and test package on disk. No topology needs to exist in TrueFidelity Cloud.
Two ECUs run Python. A third runs a compiled C++ binary on an emulated S32K344
Cortex-M7. The package contains the source and build script for all three.

```text
Test runner ↔ Vehicle CAN ↔ Gateway (Python) ↔ Internal CAN
                                                 ├── Receiver (Python)
                                                 └── C++ responder (ARM ELF)
```

The gateway routes requests and replies across both networks. Each responder has
its own CAN identifiers:

| Responder | Request ID / payload | Reply ID / payload |
| --- | --- | --- |
| Python receiver | `0x123`: `PING` + four bytes | `0x124`: `PONG` + the same four bytes |
| C++ responder | `0x125`: `PING` + four bytes | `0x126`: `CPP!` + the same four bytes |

Every case waits for the C++ firmware's ready log before sending traffic to the
shared bus. The tests check replies and malformed-input rejection. The C++ case
observes the firmware's own transmission and checks the gateway's returned frame.
All three ECUs and test deadlines use simulation time.

The Python ECUs register `@handlers.on_frame(...)` callbacks from `truefidelity_sdk`.
`await handlers.run_coordinated(ecu)` dispatches frames on the shared ECU clock.
Handlers send through `await ecu.can(...).send(...)`; they do not use host threads
or wall-clock sleeps. This requires the development runner with coordinated
decorator support. The C++ build includes debug symbols.

## Build and validate

You need Python 3, the TF CLI, Clang with ARM target support, and LLVM LLD. The
builder finds `ld.lld` on PATH or in an installed Rust toolchain. No Zephyr SDK,
C++ standard library, or downloaded firmware is needed.

From this directory:

```bash
python3 build.py
tf test validate -f tests/nightly.yaml
```

The build creates `build/ecus.zip` and `build/cpp-responder.elf`. It executes no ECU
code. Both artifacts are reproducible with the same sources and toolchain.
Validation needs no login and deploys nothing.

The script invokes Clang and LLD directly. Use `--clang /path/to/clang++` and
`--linker /path/to/ld.lld` to select your toolchain. Use `--profile debug` for
`-Og` builds; the default release build uses `-Os`. Both include debug symbols.

The C++ example is freestanding firmware for ECUSim's S32K344 model. It initializes
FlexCAN0, polls its receive mailbox, and logs through LPUART2. It is not a physical
board bring-up example: clocks, pin routing, watchdogs, and interrupts would need
hardware-specific initialization.

## Open in VS Code

1. Click **+** in TrueFidelity's **Projects** heading, or run **TrueFidelity: Add Local Project…**.
2. Select this directory, `can-gateway-iac`, not its `tests` subdirectory.
3. Expand the topology to see Gateway, Receiver, and C++ responder. Open `topology.yaml` to edit the network wiring.
4. Expand **Testing**. Use **Validate** or **Run Test** on a case or the nightly suite.

Source folders appear automatically under each ECU. Gateway and Receiver share
`ecus/`; C++ responder uses `ecus/cpp-responder/`. Right-click an ECU and select
**Build**. The checked-in folder settings run `build.py` and write the artifacts
to the paths in `topology.yaml`. Python builds do not need a C++ toolchain.
Use **Edit Build Settings** to change the command or **Set Source Folder** to
replace a detected folder. Building does not contact TrueFidelity Cloud.

Standalone cases automatically use this project's `topology.yaml`. The suite owns its
topology reference. Opening or removing the project does not import or delete anything in TrueFidelity Cloud.

## Run in the cloud

The checked-in YAML pins published development runtime images. For another
environment, replace these references with images its test runner accepts:

| File | Value to set |
| --- | --- |
| `topology.yaml` | Gateway and Receiver `image` fields: your approved Python runtime digest |
| `topology.yaml` | C++ responder `image`: your approved S32K344 ECUSim runtime digest |

No saved cloud project is needed. Execution uses your active organization or private
account, deploys the topology on demand, and tears it down after the tests.

```bash
tf auth login
tf test run -f tests/nightly.yaml --root . --results tf-results/
```

Each case gets a fresh environment. The runner tears it down and writes JSON, JUnit,
HTML, and configured logs/traffic under `tf-results/`. This command does not import definitions.

Development cloud run `d4d2d1ec-e929-4cdd-b6e3-ad1773875f5b` passed all three
cases and 11 checks on 8 September 2026. Acceptance through completed cleanup took
19 seconds, with no saved cloud project. The CLI downloaded reports and traffic.

To run one case from the CLI:

```bash
tf test run -f tests/echo.yaml --topology topology.yaml --root . --results tf-results/
```

## Files

| Path | Purpose |
| --- | --- |
| `topology.yaml` | Three ECU specs, binary/archive paths, resources, and both CAN networks |
| `ecus/*.py` | Gateway and Python receiver source code |
| `ecus/cpp-responder/` | C++ source, reset startup, and S32K344 linker script |
| `tests/echo.yaml` | Exact PING/PONG exchange across both networks |
| `tests/reject.yaml` | Wrong header and short payload produce no response |
| `tests/cpp.yaml` | C++ startup, rejection checks, exact replies, and mailbox reuse |
| `tests/nightly.yaml` | Fresh-environment suite and report/traffic settings |
| `build.py` | Reproducible Python archive and ARM C++ firmware builder |
| `verify.py` | Repeatable package and optional runtime checks |

## Verify changes to the demo

```bash
python3 verify.py --tf /path/to/tf
```

For a TF development checkout, the existing runtime harness can execute the package
locally without a cloud deployment. Build it in `cloud` with
`cargo build -p tf-test-runtime --example run-pingpong`, then run:

```bash
python3 verify.py --tf /path/to/tf \
  --runner /path/to/cloud/target/debug/examples/run-pingpong \
  --sdk-source /path/to/cloud/sdk/testing/src \
  --ecusim /path/to/ECUSim/build/qemu-system-arm
```

Use an ECUSim build with the private ECU-time CAN and console adapters. The harness
boots the compiled C++ ELF and runs both Python ECUs for each of the three cases.
It checks the results and complete teardown, with a 30-second wall-clock budget.
It pulls no images and deploys nothing to the cloud. Keep the sample image digests
for this harness check; they select the supplied local executables.
