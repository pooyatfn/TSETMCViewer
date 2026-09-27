"""Leader election for collector replicas (ADR 0010).

Several collector containers may run for availability; exactly one should call
TSETMC. They compete for a Redis lease: the holder renews it every
``renew_every`` seconds, and if it dies the lease expires after ``ttl`` and a
standby takes over. Duplicate work during a hand-over is harmless — ticks are
keyed on (fund, minute) in a ReplacingMergeTree — so the design favours
availability: without Redis, or when Redis errors, every replica leads.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from uuid import uuid4

from tsetmc_viewer import telemetry
from tsetmc_viewer.storage.tickbus import TickBus

log = logging.getLogger(__name__)

LEASE_NAME = "tsetmc:collector:leader"


class Leadership:
    def __init__(self, bus: TickBus, ttl_seconds: float = 60, renew_every: float = 15) -> None:
        if renew_every * 2 > ttl_seconds:
            raise ValueError("renew at least twice per lease period")
        self._bus = bus
        self._ttl_ms = int(ttl_seconds * 1000)
        self._renew_every = renew_every
        self.owner = f"{socket.gethostname()}:{uuid4().hex[:8]}"
        self.is_leader = False

    async def check(self) -> bool:
        """Acquire or renew the lease; returns whether this replica leads now."""
        result = await self._bus.lease(LEASE_NAME, self.owner, self._ttl_ms)
        leader = True if result is None else result  # no Redis → single-node mode
        if leader != self.is_leader:
            log.info(
                "leadership acquired" if leader else "leadership lost: standing by",
                extra={"owner": self.owner, "single_node": result is None},
            )
        self.is_leader = leader
        telemetry.LEADER.set(int(leader))
        return leader

    async def keep(self, stop: asyncio.Event) -> None:
        """Background renewal until ``stop``; then hand the lease over immediately."""
        try:
            while not stop.is_set():
                await self.check()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._renew_every)
        finally:
            await self.resign()

    async def resign(self) -> None:
        if self.is_leader:
            await self._bus.release(LEASE_NAME, self.owner)
            self.is_leader = False
            telemetry.LEADER.set(0)
            log.info("leadership released", extra={"owner": self.owner})
