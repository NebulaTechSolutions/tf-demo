from dataclasses import dataclass
from typing import AsyncIterator

import truefidelity.testing as tf


@dataclass(frozen=True)
class ClockWindow:
    minimum_ns: int
    maximum_ns: int


_setups = 0


@tf.fixture(name="pingpong-environment", timeout="1ms", scope="environment")
async def environment(ctx: tf.Context, inputs: dict[str, int]) -> AsyncIterator[int]:
    global _setups
    _setups += 1
    print("ping-pong environment fixture setup")
    yield _setups
    print("ping-pong environment fixture cleanup")


@tf.check(name="pingpong-clock-and-fixture", timeout="1ms")
async def verify_environment(ctx: tf.Context, inputs: ClockWindow) -> None:
    setups = await ctx.fixture(environment, {})
    before = ctx.clock.now_ns()
    await ctx.sleep("1ns")
    now = ctx.clock.now_ns()
    ctx.assert_that(now == before + 1, name="python-uses-ecu-clock")
    ctx.assert_that(inputs.minimum_ns <= now <= inputs.maximum_ns,
                    name="fresh-or-continued-clock", evidence={"ecu_time_ns": now})
    ctx.assert_that(setups == 1, name="one-fixture-per-environment")
