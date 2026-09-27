"""Response caching for analytics endpoints (ADR 0006, layers ④ and ⑤).

``cached_json`` implements cache-aside keyed on (route, params, tick):

1. Build the ETag from the same key. If the browser already has it → 304.
2. Look the key up in Redis → serve the stored bytes.
3. Otherwise compute (ClickHouse), serialise once, store with a short TTL.

``Cache-Control: max-age`` is the number of seconds until the next tick, so a
browser never re-asks before new data can exist.

Misses are *single-flight*: when a new tick arrives, every open panel asks for the
same keys at once; only the first request computes, the others await its result
(Day 6 load test: 56 → 6 ClickHouse queries for 20 users at a new tick). Two layers:
an in-process future, and a Redis lock across API worker processes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from pydantic import BaseModel, TypeAdapter

from tsetmc_viewer import telemetry
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.storage.tickbus import TickBus

CACHE_TTL_SECONDS = 120
_ANY = TypeAdapter(Any)
_inflight: dict[str, asyncio.Future[bytes]] = {}


def _serialise(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        return value.model_dump_json().encode()
    return _ANY.dump_json(value)


def cache_key(route: str, params: Mapping[str, Any], tick: str) -> str:
    digest = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    return f"api:{route}:{digest[:16]}:{tick}"


def versioned(tick: str, clock: MarketClock) -> str:
    """The data version a cached answer belongs to: the tick *and* the market phase.

    Answers also depend on the clock (``is_live``, the holiday banner): one cached while
    the market was open must not be served, or 304'd, after it closed — even when the
    collector is down and no new tick ever arrives.
    """
    return f"{tick}|{'open' if clock.is_open(clock.now()) else 'closed'}"


async def cached_json(
    request: Request,
    *,
    route: str,
    params: Mapping[str, Any],
    compute: Callable[[], Awaitable[Any]],
    bus: TickBus,
    clock: MarketClock,
) -> Response:
    tick: str = getattr(request.state, "tick", None) or await bus.current()
    key = cache_key(route, params, versioned(tick, clock))
    etag = f'W/"{hashlib.sha1(key.encode()).hexdigest()[:20]}"'
    max_age = int(clock.seconds_until_next_tick(clock.now(), 60)) + 1 if tick != "none" else 0
    headers = {"ETag": etag, "Cache-Control": f"private, max-age={max_age}", "X-Tick": tick}

    if tick != "none" and request.headers.get("if-none-match") == etag:
        telemetry.API_CACHE.labels("not_modified").inc()
        return Response(status_code=304, headers=headers)

    body = await bus.get(key) if tick != "none" else None
    if body is not None:
        headers["X-Cache"] = "hit"
    elif tick == "none":
        headers["X-Cache"] = "miss"  # no tick known (no Redis): nothing can be shared
        body = _serialise(await compute())
    else:
        shared = key in _inflight
        headers["X-Cache"] = "shared" if shared else "miss"
        body = await _single_flight(key, compute, bus)
    telemetry.API_CACHE.labels(headers["X-Cache"]).inc()
    return Response(content=body, media_type="application/json", headers=headers)


async def _single_flight(key: str, compute: Callable[[], Awaitable[Any]], bus: TickBus) -> bytes:
    """Compute ``key`` once even if many requests miss it at the same moment."""
    if (pending := _inflight.get(key)) is not None:
        return await asyncio.shield(pending)
    future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
    _inflight[key] = future
    try:
        body = await _across_processes(key, compute, bus)
        future.set_result(body)
        return body
    except BaseException as exc:
        future.set_exception(exc)
        future.exception()  # mark retrieved: waiters re-raise it, no "never retrieved" noise
        raise
    finally:
        del _inflight[key]


LOCK_TTL_MS = 10_000  # longer than any analytics query; a crashed holder frees it by expiry
WAIT_STEP_SECONDS = 0.05


async def _across_processes(key: str, compute: Callable[[], Awaitable[Any]], bus: TickBus) -> bytes:
    """Second layer: one computation per key across *all* API worker processes (ADR 0010).

    The first process to take the Redis lock computes and stores the result; the others
    poll the cache until it appears. If the holder takes too long (or dies), they stop
    waiting and compute themselves: a lock can delay a response, never lose one.
    """
    owner = uuid4().hex
    acquired = await bus.lease(f"lock:{key}", owner, LOCK_TTL_MS)
    if acquired is False:  # another process is computing this key right now
        for _ in range(int(LOCK_TTL_MS / 1000 / WAIT_STEP_SECONDS)):
            await asyncio.sleep(WAIT_STEP_SECONDS)
            if (body := await bus.get(key)) is not None:
                return body
    try:
        body = _serialise(await compute())
        await bus.set(key, body, CACHE_TTL_SECONDS)
        return body
    finally:
        if acquired:
            await bus.release(f"lock:{key}", owner)
