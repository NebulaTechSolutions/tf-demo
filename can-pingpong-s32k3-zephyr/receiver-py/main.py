"""Python pong receiver — DBC-aware Script ECU.

Listens for PING_Message (0x123) on a CAN bus and replies with
PONG2_Response (0x125) using named DBC signals via `truefidelity_sdk`.
Two ECUs cannot share a CAN arbitration ID without colliding on the bus,
so this script-ECU answers on its own ID; payload layout mirrors
PONG_Response.

Local development: drop a `pingpong.dbc` next to this file and run with
python main.py. On the platform, the DBC is auto-injected via
TRUEFIDELITY_DBC_FILES, and the load_dbc() call below is a no-op when
the file isn't present.
"""

import os
import time

from truefidelity_sdk import ECU

ecu = ECU()

# First CAN bus the platform attached to this ECU.
can_bus = next(
    (name for name, iface in ecu.interfaces().items()
     if iface.type in ("can", "can-fd")),
    None,
)
if can_bus is None:
    raise SystemExit("no CAN interface attached to this ECU")

# Local-dev fallback. Silently no-ops on the platform — `ecu.run()` then
# falls back to whatever DBC the platform injected for this bus.
ecu.load_dbc(os.path.join(os.path.dirname(__file__), "pingpong.dbc"))

start_time_ms = int(time.monotonic() * 1000)
ping_count = 0


@ecu.on_message(bus=can_bus, message="PING_Message")
def handle_ping(msg):
    global ping_count
    ping_count += 1

    sequence = msg.signals["SequenceCounter"]
    ping_ts = msg.signals["TimestampOffset"]

    now_ms = int(time.monotonic() * 1000)
    our_ts = (now_ms - start_time_ms) & 0xFFFF
    rtt = (our_ts - ping_ts) & 0xFFFF if our_ts >= ping_ts else 0

    ecu.send_message(
        bus=can_bus,
        message="PONG2_Response",
        signals={
            "EchoCounter": sequence,
            "ProcessingTime": 0,
            "RoundTripTime": rtt,
        },
    )
    print(
        f"[py-receiver] PING #{ping_count} seq={sequence} -> PONG2 rtt={rtt}ms",
        flush=True,
    )


if __name__ == "__main__":
    print(f"[py-receiver] listening for PING on {can_bus}", flush=True)
    ecu.run()
