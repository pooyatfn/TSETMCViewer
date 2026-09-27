"""The "tick" event: how the collector tells the API that new data is committed.

One Redis instance serves two purposes (ADR 0006):
- ``tsetmc:tick`` key: the id of the latest committed tick. Response-cache keys
  embed it, so a new tick makes every cached response stale at once without
  deleting anything.
- ``tsetmc:ticks`` pub/sub channel: pushed to browsers through SSE.

Redis is an optimisation, never a dependency: every method fails open (logs
and returns a neutral value) so the collector keeps collecting and the API
keeps serving from ClickHouse when Redis is down.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

log = logging.getLogger(__name__)

# Leases are "SET if absent, else renew if mine" — one atomic script, so a replica can
# never extend a lease another replica just acquired (ADR 0010).
_LEASE = """
local v = redis.call('GET', KEYS[1])
if not v then
  redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
  return 1
end
if v == ARGV[1] then
  redis.call('PEXPIRE', KEYS[1], ARGV[2])
  return 1
end
return 0
"""
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""

TICK_KEY = "tsetmc:tick"
TICK_CHANNEL = "tsetmc:ticks"


class TickBus:
    def __init__(self, redis: Redis | None) -> None:
        self._redis = redis

    @classmethod
    def from_url(cls, url: str) -> TickBus:
        return cls(Redis.from_url(url, decode_responses=False) if url else None)

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    async def publish(self, tick: datetime, payload: dict[str, Any]) -> None:
        """Called by the collector after a cycle's rows are committed."""
        if self._redis is None:
            return
        message = json.dumps({"tick": tick.isoformat(), **payload}, default=str)
        try:
            await self._redis.set(TICK_KEY, tick.isoformat())
            await self._redis.publish(TICK_CHANNEL, message)
        except RedisError as exc:
            log.warning("tick publish failed", extra={"error": str(exc)})

    async def bump(self, reason: str) -> None:
        """Announce new rows that belong to an already-published tick (e.g. a backfill).

        The tick id is what every cache key and ETag hangs on, so data written under an
        unchanged tick would stay invisible behind cached answers and 304s. A suffixed id
        invalidates them, and the message makes open panels refetch.
        """
        if self._redis is None:
            return
        current = await self.current()
        if current == "none":
            return
        base = current.split("#", 1)[0]  # not "+": an ISO tick has "+03:30" in it
        try:
            await self._redis.set(TICK_KEY, f"{base}#{reason}.{time.time_ns()}")
            await self._redis.publish(TICK_CHANNEL, json.dumps({"tick": base, "reason": reason}))
        except RedisError as exc:
            log.warning("tick bump failed", extra={"error": str(exc)})

    async def current(self) -> str:
        """Latest committed tick id, or ``"none"`` when unknown."""
        if self._redis is None:
            return "none"
        try:
            value = await self._redis.get(TICK_KEY)
        except RedisError as exc:
            log.warning("tick read failed", extra={"error": str(exc)})
            return "none"
        return value.decode() if isinstance(value, bytes) else "none"

    async def get(self, key: str) -> bytes | None:
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(key)
        except RedisError as exc:
            log.warning("cache read failed", extra={"error": str(exc)})
            return None
        return value if isinstance(value, bytes) else None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(key, value, ex=ttl_seconds)
        except RedisError as exc:
            log.warning("cache write failed", extra={"error": str(exc)})

    async def subscribe(self) -> AsyncGenerator[bytes, None]:
        """Yield tick messages as they are published (for SSE)."""
        if self._redis is None:
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(TICK_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(TICK_CHANNEL)
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    # --- leases (collector leadership, distributed single-flight) ---------------------------
    async def lease(self, name: str, owner: str, ttl_ms: int) -> bool | None:
        """Acquire or renew ``name`` for ``owner``. ``None`` = no Redis / Redis error."""
        if self._redis is None:
            return None
        try:
            return bool(await self._redis.eval(_LEASE, 1, name, owner, str(ttl_ms)))
        except RedisError as exc:
            log.warning("lease failed", extra={"lease": name, "error": str(exc)})
            return None

    async def release(self, name: str, owner: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.eval(_RELEASE, 1, name, owner)
        except RedisError as exc:
            log.warning("lease release failed", extra={"lease": name, "error": str(exc)})
