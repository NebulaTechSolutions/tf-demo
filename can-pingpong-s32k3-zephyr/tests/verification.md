# Verify the demo locally

The local checks below do not create a cloud topology or publish definitions.

## Development cloud result

On 8 September 2026, run `431c377e-b4e3-4a60-8c81-9a526de19121`
passed all four nightly cases and 15 checks in the development cluster.
Acceptance through completed cleanup took 105 seconds. The CLI downloaded the
canonical result and configured reports. The test pod and input Secret were gone
after cleanup.

This run had no saved cloud project. The fresh and continued pair cases shared
one environment. The reset case used a new environment. Test definitions stayed
on disk. The run used the development runtime digests pinned in the topology YAML.

## Verify Python and package preparation

Run from `can-pingpong-s32k3-zephyr` with existing ARM ELF builds.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/verify.py \
  --sender sender/build/release/zephyr/zephyr.elf \
  --receiver receiver/build/release/zephyr/zephyr.elf \
  --tf /path/to/tf \
  --sdk-source /path/to/sdk/testing/src
```

The preparation tests cover all 256 Python reply counters, rejected inputs, timestamp wrapping, the ECU entrypoint, and decorator metadata. They also validate all suites with the actual CLI, compare prepared packages and their portable receipts, and reject missing firmware, invalid ELF headers, symlinks, mutable image tags, and output overwrites.

Preparation checks image references offline. They do not prove that the registry is reachable or that the images can run.

## Execute the real receiver firmware

Use an ECUSim build with the private ECU-time CAN and console adapters. The script imports the QMP helper from the matching ECUSim source checkout.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/verify_firmware.py \
  --qemu "$ECUSIM_BINARY" \
  --ecusim-source /path/to/ECUSim \
  --receiver receiver/build/release/zephyr/zephyr.elf
```

The command boots the ELF, waits for the ready log, injects the same five inputs as the receiver YAML, and checks actual firmware transmissions. It stops and drains at every output boundary, as required by the private adapters.

Success prints `passed: true`, the firmware hash, the observed frames, and their ECU timestamps. A failed assertion exits nonzero.

## Run the firmware suites locally

Run all three suites through the production runner with the unchanged demo ELF and
YAML files. The output directory must not exist.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/verify_suites.py \
  --runner /path/to/run-pingpong \
  --qemu "$ECUSIM_BINARY" \
  --sdk-source /path/to/sdk/testing/src \
  --sender sender/build/release/zephyr/zephyr.elf \
  --receiver receiver/build/release/zephyr/zephyr.elf \
  --output /tmp/pingpong-suite-event
```

`verify_suites.py` uses a 30-second wall-clock budget for each suite unless you
pass `--wall-seconds`. It runs the receiver suite, the nightly suite, and the mixed
suite. The nightly suite covers fresh, continued, and reset environments.

The local debug-build qualification in
`/tmp/pingpong-suite-event-timer-20260907/qualification.json` completed cleanup for
every suite. The receiver suite took 1.203 seconds for six checks. The nightly suite
took 13.159 seconds for four cases and 15 checks. The mixed suite took 5.271 seconds
for four checks. This is local runner qualification. It is not a deployed cloud-suite
result.

## Scheduler and reconstruction limits

The coordinator advances a qualified ECU to its next output or test deadline,
whichever comes first. It does not use one-nanosecond interval barriers. The runner
adds no CAN delay, and `icount shift=0` retains instruction-time accounting.

If an incoming CAN frame invalidates work an ECU has executed ahead, the runner
recreates that ECU and replays its recorded inputs to the committed time.
Raw CAN and LPUART2 output must match the committed history during replay.
The profile accepts only the qualified S32K344 configuration with private CAN and
console adapters and no external network peer.

Each ECU can record 65,536 inputs and reconstruct 1,024 times. Across its
reconstructions, each ECU has a budget of 1,000,000 replay stops, 24 hours of replayed
ECU time, and 300 seconds of replay wall time. The run wall-clock watchdog is a
separate limit. Any exhausted limit is an infrastructure error, not an assertion
failure.

The Python unit tests use a controlled ECU interface to check entrypoint behavior.
They do not replace the mixed-topology suite.
