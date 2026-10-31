from truefidelity.testing.ecu import CanFrame
from truefidelity_sdk import ECU


def reply(frame):
    if frame.is_extended or frame.id != 0x123 or len(frame.data) != 8:
        return None
    if frame.data[:4] != b"PING":
        return None
    return CanFrame(0x124, b"PONG" + frame.data[4:])


async def main(ecu):
    handlers = ECU()
    bus = ecu.can("can0")

    @handlers.on_frame(bus="can0", id=0x123)
    async def respond(frame):
        response = reply(frame)
        if response is not None:
            await bus.send(response)

    await handlers.run_coordinated(ecu)
