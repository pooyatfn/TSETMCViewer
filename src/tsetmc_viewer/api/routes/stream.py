"""Server-Sent Events: push "new tick" notifications to open panels (ADR 0006 ⑥)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from tsetmc_viewer import telemetry
from tsetmc_viewer.api.deps import Bus
from tsetmc_viewer.storage.tickbus import TickBus

router = APIRouter(prefix="/api/v1", tags=["stream"])
KEEPALIVE_SECONDS = 15.0


async def tick_events(
    bus: TickBus, keepalive: float = KEEPALIVE_SECONDS
) -> AsyncGenerator[bytes, None]:
    """SSE frames: ``event: tick`` for every committed tick, comments as keep-alive."""
    yield f"event: hello\ndata: {await bus.current()}\n\n".encode()
    messages = bus.subscribe()
    pending: asyncio.Task[bytes] | None = None
    telemetry.SSE_CLIENTS.inc()
    try:
        while True:
            pending = pending or asyncio.ensure_future(anext(messages))
            done, _ = await asyncio.wait({pending}, timeout=keepalive)
            if not done:
                yield b": keep-alive\n\n"
                continue
            try:
                data = pending.result()
            except StopAsyncIteration:
                return
            pending = None
            yield b"event: tick\ndata: " + data + b"\n\n"
    finally:
        telemetry.SSE_CLIENTS.dec()
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        await messages.aclose()


@router.get("/stream", response_class=StreamingResponse)
async def stream(bus: Bus) -> StreamingResponse:
    """``EventSource`` endpoint. Reconnects are handled by the browser."""
    return StreamingResponse(
        tick_events(bus),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
