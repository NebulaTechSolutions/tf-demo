# Ping-pong test behavior

## Files

| File | Purpose |
| --- | --- |
| `topology-receiver.yaml` | Receiver firmware, S32K344 specification, CAN connection, and DBC. |
| `topology-firmware.yaml` | Sender and receiver firmware on the same 500 kbit/s CAN bus. |
| `topology-mixed.yaml` | Firmware pair plus `receiver2`, its Python bundle, and its entrypoint. |
| `receiver-inputs.yaml` | Boot log, rejected inputs, and valid counter boundaries. |
| `exchange.yaml` | Sender and firmware receiver agree on counter `1`. |
| `continue.yaml` | The same running pair advances to counter `2`. |
| `mixed-exchange.yaml` | PING, PONG, and PONG2 all carry counter `1`. |
| `python/checks.py` | Typed `@tf.check`, environment `@tf.fixture`, and ECU-clock assertions. |
| `python/receiver.py` | Coordinated script ECU. Uses `ecu.now_ns()`, never host time. |

Each topology specifies its ECU images, firmware files, board or script type, resources, CAN membership, bitrate, and DBC. The test runner does not look up a saved topology.

## Input and response checks

`receiver-inputs.yaml` waits up to 100 ms of ECU time for the receiver's ready log. It then sends three malformed frames, with a 20 ms no-response window after each.

Valid PING frames carry counters `0` and `255`. Each response must arrive within 50 ms, use CAN ID `0x124`, and begin with `PONG` plus the matching counter. The test sends the next valid frame only after the previous reply.

Raw stimuli include the ASCII `PING` bytes. The DBC describes the signals at bytes 4 through 7, but does not encode the header. Sending only DBC signals would produce an invalid request.

The firmware-pair tests observe sender and receiver transmissions in parallel. Each observation checks the same sequence counter. Waiting for counter `1` avoids depending on which ECU finishes booting first.

## Time and continuation

All windows use the coordinated ECU clock. The sender waits for a reply for up to 50 ms, then sleeps for one second. The tests allow up to 1800 ms for the selected exchange; they do not assert an exact one-second period.

The Python check records its ECU timestamp, sleeps for one ECU nanosecond, and checks the increment. It also checks the absolute clock window and confirms that the environment fixture was set up once.

| Case | Environment | Expected counter | Absolute ECU-time window |
| --- | --- | --- | --- |
| `pair-fresh` | New | `1` | 1 to 1.8 seconds |
| `pair-continued` | Reused | `2` | 2 to 3.6 seconds |
| `pair-reset` | New | `1` | 1 to 1.8 seconds |

The fixture stays alive for the continuation case. A reset creates a new fixture and restarts the ECUs. Suites use `failFast: true`; the default continuation failure policy also stops the chain.

## Reports and recordings

All suites request JSON, JUnit, and HTML reports, test logs, environment logs, assertion evidence, and portal history.

Full CAN recording is off in the receiver and nightly suites. The mixed suite enables it for `can`. Edit `spec.outputs.traffic.buses.can` to change that choice. Disabling the full recording does not remove the evidence needed for assertions.

The topology and test files stay in the submitted package unless you explicitly use `--import`. Portal run history and stored definitions are separate choices.

## Python receiver

`python/receiver.py` responds on `0x125`, so it does not compete with firmware PONG frames on `0x124`. It rejects extended frames, incorrect lengths, wrong IDs, and wrong headers.

The payload matches the firmware format. Processing time is zero because this behavioral model adds no processing delay. Its estimated round-trip field uses elapsed ECU milliseconds and the firmware's wrap-and-clamp calculation. It is not a measurement of physical bus latency.

The existing `receiver-py/main.py` remains the legacy portal behavioral model. It uses a different SDK and host time, and sends DBC signals without the ASCII `PONG` header. Its payload is not byte-identical to this receiver's payload. Do not use that entrypoint in coordinated tests.
