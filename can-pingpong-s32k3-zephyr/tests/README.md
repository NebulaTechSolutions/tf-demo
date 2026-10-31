# Run the ping-pong tests

Deploy the ECUs from YAML, check their CAN traffic, collect reports, and tear them down. No saved portal topology is needed.

![The firmware pair shares a CAN bus; the mixed suite adds a Python receiver.](topology.svg)

## Before you start

Use a TrueFidelity CLI with `tf test`, Python 3.11 or newer, and the `truefidelity.testing` SDK. Your account needs access to test-enabled S32K344 and Python runtime images.

The preparation script defaults to published development runtime images pinned by digest. For another environment, pass `--ecu-image` and `--python-image` with runtime references that environment accepts. No saved cloud project is required.

The nightly suite has passed in the development cloud with four cases and 15 checks. All three suites also pass through the local production runner. See [verification and limits](verification.md) for timings and limits.

## Build and prepare

Run these commands from `can-pingpong-s32k3-zephyr`.

```sh
./build.sh release
```

Prepare the firmware, DBC, and Python bundle beside the authored tests. This is the layout used by the VS Code tree.

```sh
python3 tests/prepare.py \
  --sender sender/build/release/zephyr/zephyr.elf \
  --receiver receiver/build/release/zephyr/zephyr.elf \
  --output tests --in-place
```

For a source checkout of the SDK, add `--sdk-source /path/to/sdk/testing/src`. For a CLI outside `PATH`, add `--tf /path/to/tf`.

The command validates all three suites. It prints `valid: true` and `execution_ready: false`. Offline validation checks files and contracts; it does not check cluster access or runtime availability. `preparation.json` records file hashes and validation results.

Rerun this command after rebuilding firmware. It validates the package before replacing generated artifacts. Your test cases stay in place. To freeze a separate CI package, omit `--in-place` and use a new `--output` directory.

## Run the receiver checks

Sign in to the intended environment with `tf auth login`. Confirm the API target before submitting a run.

```sh
tf test run \
  -f tests/receiver-suite.yaml \
  --root tests \
  --results tests/results
```

The receiver must ignore a wrong header, a short frame, and a wrong CAN ID. It must then reply with counters `0` and `255`.

The CLI waits for results and cleanup. Inspect the JSON, JUnit, and HTML reports under the results directory. A runtime or infrastructure error is not an assertion failure.

## Run the other suites

Use the same package with a different suite file.

| Suite | What it checks |
| --- | --- |
| `receiver-suite.yaml` | One firmware ECU, valid and malformed inputs. |
| `nightly.yaml` | Receiver checks, then the firmware pair in fresh, continued, and reset environments. |
| `mixed-suite.yaml` | Firmware pair plus the ECU-time Python receiver on CAN ID `0x125`. |

```sh
tf test run -f tests/nightly.yaml \
  --root tests --results tests/results-nightly
```

Each suite stops on the first failure. In `nightly.yaml`, `pair-continued` reuses `pair-fresh`. `pair-reset` starts another environment. See [test behavior](reference.md) for the assertions and output settings.

## Keep CI definitions in Git

Commit the authored YAML and Python files. Supply each CI build's ELF paths to `prepare.py`; do not edit topology definitions in the portal to update binaries.

Runs use your active organization or private account, deploy temporary cloud resources, and tear them down. They retain run history by default but do not import definitions. Add `--no-history` to skip retained history. Use `--project PROJECT_ID --import` only when you want an independent saved copy that you maintain yourself.

Upload the results directory as a CI artifact even when the run returns a nonzero exit code.
