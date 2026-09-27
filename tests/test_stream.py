from __future__ import annotations

import asyncio
from datetime import datetime

import fakeredis

from support import TEHRAN
from tsetmc_viewer.api.routes.stream import tick_events
from tsetmc_viewer.storage.tickbus import TickBus

TICK = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)


async def test_sse_frames_hello_keepalive_and_tick() -> None:
    bus = TickBus(fakeredis.FakeAsyncRedis())
    events = tick_events(bus, keepalive=0.05)
    assert (await anext(events)).startswith(b"event: hello")
    assert await anext(events) == b": keep-alive\n\n"

    async def publish_later() -> None:
        await asyncio.sleep(0.01)
        await bus.publish(TICK, {"funds": 159})

    task = asyncio.create_task(publish_later())
    frame = b""
    while not frame.startswith(b"event: tick"):
        frame = await anext(events)
    await task
    assert b'"tick": "2026-09-26T10:00:00+03:30"' in frame
    assert b'"funds": 159' in frame
    await events.aclose()
    assert await bus.current() == TICK.isoformat()
