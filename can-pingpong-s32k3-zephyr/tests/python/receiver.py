"""PONG2 receiver for the coordinated test runtime."""

from truefidelity.testing.ecu import CanFrame


def reply_to(frame: CanFrame, now_ns: int, started_ns: int) -> CanFrame | None:
    if frame.extended or frame.identifier != 0x123 or len(frame.data) != 8:
        return None
    if frame.data[:4] != b"PING":
        return None
    timestamp_ms = ((now_ns - started_ns) // 1_000_000) & 0xFFFF
    ping_ms = int.from_bytes(frame.data[6:8], "little")
    rtt_ms = max(0, timestamp_ms - ping_ms)
    data = b"PONG" + bytes([frame.data[4], 0]) + rtt_ms.to_bytes(2, "little")
    return CanFrame(0x125, data)


async def main(ecu):
    bus = ecu.can("can0")
    started_ns = ecu.now_ns()
    while True:
        received = await bus.receive()
        reply = reply_to(received.frame, ecu.now_ns(), started_ns)
        if reply is not None:
            await bus.send(reply)
