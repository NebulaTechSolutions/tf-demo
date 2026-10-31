from truefidelity.testing.ecu import CanFrame
from truefidelity_sdk import ECU


async def main(ecu):
    handlers = ECU()
    vehicle = ecu.can("can0")
    internal = ecu.can("can1")

    @handlers.on_frame(bus="can0", id=0x123)
    @handlers.on_frame(bus="can0", id=0x125)
    async def request(frame):
        if not frame.is_extended:
            await internal.send(CanFrame(frame.id, frame.data))

    @handlers.on_frame(bus="can1", id=0x124)
    @handlers.on_frame(bus="can1", id=0x126)
    async def response(frame):
        if not frame.is_extended:
            await vehicle.send(CanFrame(frame.id, frame.data))

    await handlers.run_coordinated(ecu)
