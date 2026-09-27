from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

import fakeredis
import httpx
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from support import TEHRAN
from tsetmc_viewer.api.cache import cache_key, cached_json
from tsetmc_viewer.api.deps import SessionDay, get_analytics, get_bus
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import MarketSettings
from tsetmc_viewer.storage.tickbus import TickBus

TICK = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)


def make_app(bus: TickBus) -> tuple[FastAPI, dict[str, int]]:
    calls = {"n": 0}
    app = FastAPI()
    clock = MarketClock(MarketSettings())

    @app.get("/thing")
    async def thing(request: Request) -> Response:
        async def compute() -> dict[str, Any]:
            calls["n"] += 1
            return {"value": calls["n"]}

        return await cached_json(
            request, route="thing", params={"a": 1}, compute=compute, bus=bus, clock=clock
        )

    return app, calls


@pytest.fixture
def bus() -> TickBus:
    return TickBus(fakeredis.FakeAsyncRedis())


def test_miss_then_hit_then_304(bus: TickBus) -> None:
    app, calls = make_app(bus)
    with TestClient(app) as client:
        client.portal.call(bus.publish, TICK, {})  # type: ignore[union-attr]
        first = client.get("/thing")
        second = client.get("/thing")
        etag = second.headers["etag"]
        third = client.get("/thing", headers={"If-None-Match": etag})
    assert (first.headers["x-cache"], second.headers["x-cache"]) == ("miss", "hit")
    assert first.json() == second.json() == {"value": 1}
    assert calls["n"] == 1  # computed once
    assert third.status_code == 304
    assert "max-age=" in first.headers["cache-control"]


def test_new_tick_invalidates_without_deleting(bus: TickBus) -> None:
    app, _ = make_app(bus)
    with TestClient(app) as client:
        client.portal.call(bus.publish, TICK, {})  # type: ignore[union-attr]
        old = client.get("/thing")
        client.portal.call(bus.publish, TICK.replace(minute=1), {})  # type: ignore[union-attr]
        new = client.get("/thing", headers={"If-None-Match": old.headers["etag"]})
    assert new.status_code == 200
    assert new.json() == {"value": 2}
    assert old.headers["etag"] != new.headers["etag"]


def test_without_redis_every_request_is_computed() -> None:
    app, _ = make_app(TickBus(None))
    with TestClient(app) as client:
        a, b = client.get("/thing"), client.get("/thing")
    assert (a.json(), b.json()) == ({"value": 1}, {"value": 2})
    assert a.headers["x-tick"] == "none"


def test_redis_down_fails_open() -> None:
    from redis.asyncio import Redis

    app, _ = make_app(TickBus(Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)))
    with TestClient(app) as client:
        resp = client.get("/thing")
    assert resp.status_code == 200
    assert resp.json() == {"value": 1}


def test_cache_key_is_stable_and_tick_scoped() -> None:
    k1 = cache_key("r", {"b": 2, "a": 1}, "t1")
    assert k1 == cache_key("r", {"a": 1, "b": 2}, "t1")
    assert k1 != cache_key("r", {"a": 1, "b": 2}, "t2")


async def test_concurrent_misses_compute_once(bus: TickBus) -> None:
    """A new tick makes every open panel miss the same keys at once (stampede)."""
    await bus.publish(TICK, {})
    calls = {"n": 0}
    app = FastAPI()
    clock = MarketClock(MarketSettings())

    @app.get("/slow")
    async def slow(request: Request) -> Response:
        async def compute() -> dict[str, Any]:
            calls["n"] += 1
            await asyncio.sleep(0.05)
            if request.query_params.get("fail"):
                raise RuntimeError("query failed")
            return {"n": calls["n"]}

        return await cached_json(
            request,
            route="slow",
            params=dict(request.query_params),
            compute=compute,
            bus=bus,
            clock=clock,
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        responses = await asyncio.gather(*(client.get("/slow") for _ in range(10)))
        assert calls["n"] == 1
        assert {r.json()["n"] for r in responses} == {1}
        assert sorted(r.headers["x-cache"] for r in responses) == ["miss"] + ["shared"] * 9

        # A failed computation fails its waiters too, and is not cached: the next try recomputes.
        failing = await asyncio.gather(
            *(client.get("/slow?fail=1") for _ in range(3)), return_exceptions=True
        )
        assert all(isinstance(r, RuntimeError) for r in failing)
        assert calls["n"] == 2


async def test_session_date_is_memoised_per_tick(bus: TickBus) -> None:
    """Cache hits and 304s must not cost a ClickHouse query for the session date."""

    class CountingAnalytics:
        calls = 0

        async def session_date(self) -> date:
            self.calls += 1
            return date(2026, 9, 23)

    analytics = CountingAnalytics()
    app = FastAPI()

    @app.get("/day")
    async def day(d: SessionDay) -> str:
        return d.isoformat()

    app.dependency_overrides[get_analytics] = lambda: analytics
    app.dependency_overrides[get_bus] = lambda: bus
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        await bus.publish(TICK, {})
        for _ in range(5):
            assert (await client.get("/day")).json() == "2026-09-23"
        assert analytics.calls == 1
        await bus.publish(TICK.replace(minute=1), {})  # new tick → look again
        await client.get("/day")
        assert analytics.calls == 2
        await client.get("/day?date=2026-09-01")  # explicit date: no lookup at all
        assert analytics.calls == 2
