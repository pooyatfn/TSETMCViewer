"""The session's edges and each fund's trading status.

Three bugs seen on a real day (1405/07/04) are pinned here:
- the last point of the day stayed at 12:29 and the panel kept saying «زنده» after the close;
- rows written after the last tick (the intraday backfill) stayed invisible behind the cache;
- a suspended fund looked like any other fund.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import fakeredis
import httpx
import respx
from fastapi import FastAPI, Request, Response

from support import BASE, EQUITY_SAMPLES, TEHRAN, MemoryStore, fixture, mock_tsetmc
from tsetmc_viewer.api.cache import cached_json
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import STATUS_EVERY_MINUTES, Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.domain.status import StatusKind, status_kind
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import parse_instrument_state
from tsetmc_viewer.storage.tickbus import TickBus

SATURDAY = datetime(2026, 9, 26, tzinfo=TEHRAN)


class MovableClock(MarketClock):
    def __init__(self, now: datetime) -> None:
        super().__init__(MarketSettings())
        self.moment = now

    def now(self) -> datetime:
        return self.moment


def at(h: int, m: int, s: int = 0) -> datetime:
    return SATURDAY.replace(hour=h, minute=m, second=s)


def make(client: TsetmcClient, store: MemoryStore, clock: MarketClock, **kw: Any) -> Collector:
    universe = FundUniverse(UniverseSync(client, store, clock), store)
    return Collector(
        client, store, clock, universe, Validator(ValidationSettings(), clock), **kw
    )  # fmt: skip


# --- status -----------------------------------------------------------------------------


def test_status_codes() -> None:
    assert status_kind("A ") is StatusKind.OPEN
    assert status_kind("AS") is StatusKind.SUSPENDED
    assert status_kind("IS") is StatusKind.SUSPENDED
    assert status_kind("AR") is StatusKind.RESERVED
    assert status_kind("AG") is StatusKind.BLOCKED
    assert status_kind("I") is StatusKind.FORBIDDEN
    assert status_kind("") is StatusKind.UNKNOWN


def test_recorded_status_parses() -> None:
    state = parse_instrument_state(fixture("closing_price_info_11427939669935844.json"))
    assert state is not None
    assert (state.code, state.title, state.under_supervision) == ("A", "مجاز", 0)


async def test_every_fund_first_then_a_fifth_per_minute(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    clock = MovableClock(at(10, 0, 5))
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, clock)
            await collector.collect_once()
            assert {s.ins_code for s in store.states} == EQUITY_SAMPLES
            store.states.clear()
            for minute in range(1, 1 + STATUS_EVERY_MINUTES):
                clock.moment = at(10, minute, 5)
                await collector.collect_once()
    seen = [s.ins_code for s in store.states]
    assert sorted(seen) == sorted(EQUITY_SAMPLES)  # each fund exactly once in five minutes


# --- the close ------------------------------------------------------------------------------


async def test_the_close_is_committed_once_at_the_closing_stamp(
    http_settings: HttpSettings,
) -> None:
    store = MemoryStore()
    clock = MovableClock(at(12, 29, 3))
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, clock)
            collector._after_cycle(await collector.collect_once())  # the 12:29 cycle
            clock.moment = at(12, 30, 2)
            await collector._close_session(clock.now())
            await collector._close_session(clock.now())  # the loop wakes again: no repeat
    assert [(r.tick.strftime("%H:%M"), r.note) for r in store.runs] == [
        ("12:29", ""),
        ("12:30", "session close"),
    ]
    assert max(t.ts for t in store.ticks) == at(12, 30)


async def test_no_close_cycle_without_a_live_session(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    clock = MovableClock(at(12, 30, 2))
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            await make(client, store, clock)._close_session(clock.now())
    assert store.runs == []  # started after the close: the bootstrap/refresh path owns that


async def test_after_close_refreshes_the_closing_stamp_even_with_minute_data(
    http_settings: HttpSettings,
) -> None:
    store = MemoryStore()
    clock = MovableClock(at(12, 29, 3))
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, clock)
            await collector.collect_once()
            clock.moment = at(13, 1)
            snapshot = await collector.closing_snapshot(SATURDAY.date(), refresh=True)
    assert snapshot is not None
    assert snapshot.tick == at(12, 30)
    assert snapshot.note == "closing snapshot"


# --- the cache after the close and after a backfill ----------------------------------------


def app_with(bus: TickBus, clock: MarketClock, calls: dict[str, int]) -> FastAPI:
    app = FastAPI()

    @app.get("/x")
    async def x(request: Request) -> Response:
        async def compute() -> dict[str, int]:
            calls["n"] += 1
            return {"n": calls["n"]}

        return await cached_json(
            request, route="x", params={}, compute=compute, bus=bus, clock=clock
        )

    return app


async def test_an_answer_cached_while_open_is_not_reused_after_the_close() -> None:
    bus = TickBus(fakeredis.FakeAsyncRedis())
    await bus.publish(at(12, 29), {})
    clock = MovableClock(at(12, 29, 30))
    calls = {"n": 0}
    transport = httpx.ASGITransport(app=app_with(bus, clock, calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        first = await client.get("/x")
        clock.moment = at(12, 31)  # no new tick: the collector could be down
        again = await client.get("/x", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 200  # not 304: is_live must be recomputed
    assert calls["n"] == 2


async def test_a_bump_invalidates_cached_answers_and_tells_panels() -> None:
    bus = TickBus(fakeredis.FakeAsyncRedis())
    await bus.publish(at(12, 29), {})
    clock = MovableClock(at(13, 0))
    calls = {"n": 0}
    transport = httpx.ASGITransport(app=app_with(bus, clock, calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        first = await client.get("/x")
        assert (
            await client.get("/x", headers={"If-None-Match": first.headers["etag"]})
        ).status_code == 304
        await bus.bump("backfill")
        after = await client.get("/x", headers={"If-None-Match": first.headers["etag"]})
    assert after.status_code == 200
    assert after.json() == {"n": 2}
    first_bump = await bus.current()
    assert first_bump.startswith(at(12, 29).isoformat() + "#backfill.")
    await bus.bump("backfill")
    assert (await bus.current()).count("#") == 1  # a second bump replaces the suffix
    assert await bus.current() != first_bump


async def test_no_bump_without_redis() -> None:
    bus = TickBus(None)
    await bus.bump("backfill")  # a no-op, not an error
    assert await bus.current() == "none"
