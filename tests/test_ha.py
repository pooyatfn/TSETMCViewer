"""High availability: collector leader election and cross-process single-flight (ADR 0010)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import fakeredis
import httpx
import pytest
import respx
from fastapi import FastAPI, Request, Response

from support import BASE, TEHRAN, MemoryStore, mock_tsetmc
from tsetmc_viewer.api import cache
from tsetmc_viewer.api.cache import cache_key, cached_json, versioned
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.heartbeat import Heartbeat
from tsetmc_viewer.collector.leadership import LEASE_NAME, Leadership
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.tickbus import TickBus

TICK = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)


@pytest.fixture
def bus() -> TickBus:
    return TickBus(fakeredis.FakeAsyncRedis())


async def test_one_leader_at_a_time_and_handover(bus: TickBus) -> None:
    a, b = Leadership(bus, 1.0, 0.25), Leadership(bus, 1.0, 0.25)
    assert await a.check()
    assert not await b.check()
    assert await a.check()  # renewing its own lease
    await a.resign()
    assert await b.check()  # immediate hand-over on a clean stop


async def test_a_dead_leader_expires(bus: TickBus) -> None:
    a, b = Leadership(bus, 0.2, 0.05), Leadership(bus, 0.2, 0.05)
    assert await a.check()
    await asyncio.sleep(0.3)  # a crashed: no renewals
    assert await b.check()
    assert not await a.check()  # and a, if it comes back, stands by


async def test_without_redis_every_replica_leads() -> None:
    assert await Leadership(TickBus(None)).check()


async def test_standby_collector_does_not_call_tsetmc(
    bus: TickBus, http_settings: HttpSettings, tmp_path: Path
) -> None:
    await bus.lease(LEASE_NAME, "other-replica", 60_000)
    clock = MarketClock(MarketSettings())
    store = MemoryStore()
    beat = Heartbeat(tmp_path / "hb.json")
    stop = asyncio.Event()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, store, clock), store)
            collector = Collector(
                client, store, clock, universe, Validator(ValidationSettings(), clock),
                heartbeat=beat, leadership=Leadership(bus, 60, 15),
            )  # fmt: skip
            asyncio.get_running_loop().call_later(0.2, stop.set)
            await collector.run_forever(60, ignore_market_hours=True, stop=stop)
            calls = router.calls.call_count
    assert calls == 0
    assert not store.runs
    assert '"state": "standby"' in (tmp_path / "hb.json").read_text()


def make_app(bus: TickBus, calls: dict[str, int]) -> FastAPI:
    app = FastAPI()
    clock = MarketClock(MarketSettings())

    @app.get("/x")
    async def x(request: Request) -> Response:
        async def compute() -> dict[str, str]:
            calls["n"] += 1
            return {"from": "this-process"}

        return await cached_json(
            request, route="x", params={}, compute=compute, bus=bus, clock=clock
        )

    return app


async def test_another_process_computing_is_awaited_not_repeated(bus: TickBus) -> None:
    await bus.publish(TICK, {})
    key = cache_key("x", {}, versioned(TICK.isoformat(), MarketClock(MarketSettings())))
    await bus.lease(f"lock:{key}", "other-worker", 10_000)  # another worker is computing
    calls = {"n": 0}

    async def other_worker_finishes() -> None:
        await asyncio.sleep(0.15)
        await bus.set(key, b'{"from":"other-worker"}', 60)

    transport = httpx.ASGITransport(app=make_app(bus, calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response, _ = await asyncio.gather(client.get("/x"), other_worker_finishes())
    assert response.json() == {"from": "other-worker"}
    assert calls["n"] == 0


async def test_a_stuck_lock_holder_delays_but_never_loses_a_response(
    bus: TickBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "LOCK_TTL_MS", 300)
    await bus.publish(TICK, {})
    key = cache_key("x", {}, versioned(TICK.isoformat(), MarketClock(MarketSettings())))
    await bus.lease(f"lock:{key}", "dead-worker", 60_000)
    calls: dict[str, Any] = {"n": 0}
    transport = httpx.ASGITransport(app=make_app(bus, calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/x")
    assert response.json() == {"from": "this-process"}
    assert calls["n"] == 1
