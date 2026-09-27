"""Rebuilding minutes missed before a late start (pipeline/backfill.py, ADR 0012)."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import respx

from support import BASE, TEHRAN, fixture
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings
from tsetmc_viewer.domain.funds import FundRef, FundType
from tsetmc_viewer.pipeline.backfill import (
    MINUTE,
    BackfillLog,
    BackfillReport,
    BackfillTick,
    HistoryTape,
    IntradayBackfill,
    SessionBackfill,
    Tape,
    missing_minutes,
    seconds_of_day,
    verify,
    verify_official,
)
from tsetmc_viewer.sources.http import RawResponse
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import PriceHistoryRow, TradeRow, parse_trades
from tsetmc_viewer.storage.repository import CollectionRun, RunStatus
from tsetmc_viewer.storage.tickbus import TickBus

DAY = date(2026, 9, 26)
NOW = datetime(2026, 9, 26, 11, 40, tzinfo=TEHRAN)
GOOD, BUNCHED, FULL, BROKEN = "1", "2", "3", "4"


def hms(h: int, m: int, s: int = 0) -> int:
    return h * 3600 + m * 60 + s


def trade(n: int, sod: int, volume: int = 100, price: int = 1000, canceled: int = 0) -> TradeRow:
    h, rem = divmod(sod, 3600)
    heven = h * 10000 + rem // 60 * 100 + rem % 60
    return TradeRow(nTran=n, hEven=heven, qTitTran=volume, pTran=price, canceled=canceled)


def steady(first: int, last: int, every: int = 30) -> list[TradeRow]:
    """One 100-unit trade every ``every`` seconds; price = 1000 + minute index."""
    return [
        trade(i + 1, s, price=1000 + (s - first) // 60)
        for i, s in enumerate(range(first, last, every))
    ]


def payload(rows: Sequence[TradeRow]) -> dict[str, Any]:
    return {"trade": [r.model_dump(by_alias=True) for r in rows]}


# --- pure functions ------------------------------------------------------------------


def test_tape_state_is_cumulative_and_ignores_cancelled_trades() -> None:
    tape = Tape(
        [
            trade(2, hms(9, 1), volume=50, price=1010),
            trade(1, hms(9, 0, 10), volume=100, price=1000),
            trade(3, hms(9, 2), volume=999, price=5, canceled=1),
        ]
    )
    assert tape.at(hms(8, 59)) is None
    state = tape.at(hms(9, 1))
    assert state is not None
    assert (state.last_price, state.volume, state.value, state.trades) == (1010, 150, 150_500, 2)
    assert tape.volume_at(hms(12, 0)) == 150  # the cancelled trade never counts


def test_verify_accepts_live_snapshots_taken_within_the_minute() -> None:
    tape = Tape(steady(hms(9, 0), hms(12, 0)))  # 2 trades a minute from 9:00
    # Live tick stamped 11:30 fetched a few seconds late: volume a little above cum(11:30).
    live = [
        (hms(11, 30), tape.volume_at(hms(11, 30, 20))),
        (hms(11, 31), tape.volume_at(hms(11, 31))),
    ]
    assert verify(tape, live).matched == 2


def test_verify_rejects_trades_stamped_after_the_live_minutes() -> None:
    """The real probe: some funds had every trade stamped after 12:00 despite a 9:00 open."""
    tape = Tape(steady(hms(12, 0), hms(12, 30)))
    live = [(hms(11, 30), 40_000), (hms(11, 31), 40_200)]
    verdict = verify(tape, live)
    assert verdict.matched == 0
    assert not verdict.passes(0.9)


def test_missing_minutes_stop_before_the_first_live_tick() -> None:
    tape = Tape(steady(hms(9, 5), hms(12, 0)))
    minutes = missing_minutes(tape, hms(9, 0), hms(9, 10))
    assert [s for s, _ in minutes] == [hms(9, m) for m in range(5, 10)]  # nothing before a trade


# --- the service ------------------------------------------------------------------------


class FixedClock(MarketClock):
    def now(self) -> datetime:
        return NOW


@dataclass
class Store:
    live: dict[str, list[tuple[datetime, int]]] = field(default_factory=dict)
    history: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    raw: list[RawResponse] = field(default_factory=list)
    ticks: list[BackfillTick] = field(default_factory=list)
    log: list[BackfillLog] = field(default_factory=list)

    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int:
        self.raw.extend(responses)
        return len(responses)

    async def load_live_volumes(self, day: date) -> dict[str, list[tuple[datetime, int]]]:
        return self.live

    async def backfilled_funds(self, day: date) -> set[str]:
        return {r.ins_code for r in self.log if r.status != "error"}

    async def insert_backfill(self, ticks: Sequence[BackfillTick]) -> int:
        self.ticks.extend(ticks)
        return len(ticks)

    async def insert_backfill_log(self, rows: Sequence[BackfillLog]) -> int:
        self.log.extend(rows)
        return len(rows)

    async def load_history_day(self, day: date) -> dict[str, tuple[int, int, int]]:
        return self.history


def at(sod: int, day: date = DAY) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=TEHRAN) + timedelta(seconds=sod)


def live_from(tape: Tape, start: int, end: int, lag: int = 5) -> list[tuple[datetime, int]]:
    return [(at(s), tape.volume_at(s + lag)) for s in range(start, end, 60)]


def fund(ins: str) -> FundRef:
    return FundRef(ins_code=ins, symbol=f"f{ins}", name="", isin="", fund_type=FundType.EQUITY)


async def test_run_stores_verified_minutes_and_rejects_the_rest(
    http_settings: HttpSettings,
) -> None:
    good, bunched = steady(hms(9, 0), hms(11, 40)), steady(hms(12, 0), hms(12, 30))
    good_tape = Tape(good)
    store = Store(
        live={
            GOOD: live_from(good_tape, hms(11, 30), hms(11, 40)),  # started 11:30
            BUNCHED: [(at(hms(11, 30)), 40_000), (at(hms(11, 31)), 40_200)],
            FULL: live_from(good_tape, hms(9, 0), hms(11, 40)),  # collector ran from the open
            BROKEN: live_from(good_tape, hms(11, 30), hms(11, 40)),
        }
    )
    bodies = {GOOD: payload(good), BUNCHED: payload(bunched), FULL: payload(good)}
    requested: list[str] = []

    def handler(request: httpx.Request, ins: str) -> httpx.Response:
        requested.append(ins)
        return httpx.Response(200, json=bodies[ins]) if ins in bodies else httpx.Response(500)

    async with TsetmcClient(BASE, http_settings) as client:
        backfill = IntradayBackfill(client, store, FixedClock(MarketSettings()))
        funds = {i: fund(i) for i in (GOOD, BUNCHED, FULL, BROKEN)}
        with respx.mock(assert_all_called=False) as router:
            router.get(url__regex=re.escape(BASE) + r"/Trade/GetTrade/(?P<ins>\d+)$").mock(
                side_effect=handler
            )
            report = await backfill.run(DAY, funds)

            assert FULL not in requested  # no gap, no request
            decided = {r.ins_code: r.status for r in store.log}
            assert decided == {GOOD: "stored", BUNCHED: "rejected", BROKEN: "error"}
            assert (report.stored, report.rejected, report.errors) == (1, 1, 1)
            assert report.rejected_symbols == (f"f{BUNCHED}",)

            stamps = sorted(t.ts for t in store.ticks)
            assert {t.ins_code for t in store.ticks} == {GOOD}
            assert stamps[0] == at(hms(9, 0))
            assert stamps[-1] == at(hms(11, 29))  # live data from 11:30 is never replaced
            assert len(stamps) == 150
            last = max(store.ticks, key=lambda t: t.ts)
            assert last.volume == good_tape.volume_at(hms(11, 29))
            assert len(store.raw) >= 3  # raw first (ADR 0003), even for rejected funds

            # Idempotent: decided funds are not fetched again; errors are retried.
            requested.clear()
            await backfill.run(DAY, funds)
            assert set(requested) == {BROKEN}  # (500 is retried by the HTTP layer)


async def test_run_only_knows_today(http_settings: HttpSettings) -> None:
    store = Store(live={GOOD: [(at(hms(11, 30)), 1)]})
    async with TsetmcClient(BASE, http_settings) as client:
        backfill = IntradayBackfill(client, store, FixedClock(MarketSettings()))
        report = await backfill.run(DAY - timedelta(days=1), {GOOD: fund(GOOD)})
    assert report.funds == 0
    assert store.log == []


# --- when the collector runs it ------------------------------------------------------


class StubBackfill:
    def __init__(self) -> None:
        self.days: list[date] = []
        self.report = BackfillReport()

    async def run(self, day: date, funds: Any) -> BackfillReport:
        self.days.append(day)
        return self.report


class StubUniverse:
    async def get(self, day: date) -> dict[str, FundRef]:
        return {GOOD: fund(GOOD)}


def cycle(minute: int, status: RunStatus = "ok") -> CollectionRun:
    tick = at(hms(11, minute))
    return CollectionRun(uuid4(), tick, tick, tick, status, requests=3, failed=0)


async def test_collector_backfills_once_after_three_live_cycles() -> None:
    stub = StubBackfill()
    collector = Collector(
        None,  # type: ignore[arg-type]  # not used on this path
        None,  # type: ignore[arg-type]
        FixedClock(MarketSettings()),
        StubUniverse(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        backfill=stub,  # type: ignore[arg-type]
    )
    statuses: list[tuple[int, RunStatus]] = [
        (30, "ok"), (31, "failed"), (32, "partial"), (33, "ok"), (34, "ok"),
    ]  # fmt: skip
    for minute, status in statuses:
        collector._after_cycle(cycle(minute, status))
        await asyncio.sleep(0)  # let a started task run
    await asyncio.sleep(0)
    assert stub.days == [DAY]  # the third *successful* cycle (11:33) started it, only once


def test_real_trade_list_parses_into_a_consistent_tape() -> None:
    """Recorded 1405/07/04 12:17 (هم تراز, 337 trades) by scripts/probe_backfill.py."""
    tape = Tape(parse_trades(fixture("trades_51920757918600374.json")))
    assert len(tape) == 337
    assert tape.first == hms(9, 1, 3)
    end = tape.at(hms(12, 30))
    assert end is not None
    assert (end.trades, end.volume, end.last_price) == (337, 8_604_103, 26_352)
    minutes = missing_minutes(tape, hms(9, 0), hms(11, 30))
    assert minutes[0][0] == hms(9, 2)  # first boundary after the first trade
    volumes = [s.volume for _, s in minutes]
    assert volumes == sorted(volumes)  # running totals never go down


# --- past sessions (ADR 0013) ---------------------------------------------------------

PAST_DAY = date(2026, 9, 20)


def price_row(
    sod: int, last_price: int, volume: int, value: int, trade_count: int
) -> PriceHistoryRow:
    h, rem = divmod(sod, 3600)
    heven = h * 10000 + rem // 60 * 100 + rem % 60
    return PriceHistoryRow(
        hEven=heven, pDrCotVal=last_price, qTotTran5J=volume, qTotCap=value, zTotTran=trade_count
    )


def price_events(first: int, last: int, every: int = 300) -> list[PriceHistoryRow]:
    """One price-change event every ``every`` seconds; volume/value/count keep rising."""
    return [
        price_row(s, 1000 + i, (i + 1) * 1000, (i + 1) * 1_000_000, i + 1)
        for i, s in enumerate(range(first, last, every))
    ]


def history_payload(rows: Sequence[PriceHistoryRow]) -> dict[str, Any]:
    return {"closingPriceHistory": [r.model_dump(by_alias=True) for r in rows]}


def test_history_tape_is_already_cumulative_no_accumulation_needed() -> None:
    tape = HistoryTape(
        [price_row(hms(10, 0), 1050, 500, 500_000, 5), price_row(hms(9, 30), 1000, 300, 300_000, 3)]
    )
    assert tape.at(hms(9, 0)) is None
    state = tape.at(hms(9, 45))
    assert state is not None
    assert (state.last_price, state.volume, state.value, state.trades) == (1000, 300, 300_000, 3)
    assert tape.last == tape.at(hms(23, 59))


def test_verify_official_is_a_single_all_or_nothing_check() -> None:
    tape = HistoryTape(price_events(hms(9, 0), hms(12, 30)))
    last = tape.last
    assert last is not None
    ok = verify_official(tape, (last.volume, last.value, last.trades))
    assert (ok.overlap, ok.matched) == (1, 1)
    assert ok.passes(1.0)

    off = verify_official(tape, (last.volume * 2, last.value, last.trades))
    assert (off.overlap, off.matched) == (1, 0)

    assert verify_official(tape, None) == verify_official(HistoryTape([]), (1, 1, 1))


async def test_session_backfill_stores_a_verified_day_and_rejects_a_mismatch(
    http_settings: HttpSettings,
) -> None:
    good = price_events(hms(9, 0), hms(12, 30))
    good_tape = HistoryTape(good)
    last = good_tape.last
    assert last is not None
    store = Store(history={GOOD: (last.volume, last.value, last.trades), BUNCHED: (1, 1, 1)})
    bodies = {GOOD: history_payload(good), BUNCHED: history_payload(good)}  # BUNCHED won't match

    def handler(request: httpx.Request, ins: str) -> httpx.Response:
        return (
            httpx.Response(200, json=bodies[ins])
            if ins in bodies
            else httpx.Response(200, json={"closingPriceHistory": []})
        )

    async with TsetmcClient(BASE, http_settings) as client:
        backfill = SessionBackfill(client, store, FixedClock(MarketSettings()))
        funds = {i: fund(i) for i in (GOOD, BUNCHED, BROKEN)}
        with respx.mock(assert_all_called=False) as router:
            router.get(
                url__regex=re.escape(BASE)
                + r"/ClosingPrice/GetClosingPriceHistory/(?P<ins>\d+)/\d+$"
            ).mock(side_effect=handler)
            report = await backfill.run(PAST_DAY, funds)

    decided = {r.ins_code: r.status for r in store.log}
    assert decided == {GOOD: "stored", BUNCHED: "rejected", BROKEN: "no_trades"}
    assert (report.stored, report.rejected) == (1, 1)
    assert {t.ins_code for t in store.ticks} == {GOOD}
    stamps = sorted(t.ts for t in store.ticks)
    close_sod = seconds_of_day(FixedClock(MarketSettings()).session_close(PAST_DAY))
    # a full session's minute grid, open to close inclusive
    assert stamps[0] == at(hms(9, 0), PAST_DAY)
    assert stamps[-1] == at(close_sod, PAST_DAY)
    assert len(stamps) == close_sod // MINUTE - hms(9, 0) // MINUTE + 1


async def test_session_backfill_never_touches_today_or_the_future(
    http_settings: HttpSettings,
) -> None:
    store = Store()
    async with TsetmcClient(BASE, http_settings) as client:
        backfill = SessionBackfill(client, store, FixedClock(MarketSettings()))
        today_report = await backfill.run(NOW.date(), {GOOD: fund(GOOD)})
        future_report = await backfill.run(NOW.date() + timedelta(days=1), {GOOD: fund(GOOD)})
    assert (today_report.funds, future_report.funds) == (0, 0)
    assert store.log == []


async def test_collector_backfill_sessions_skips_weekends_and_reports_new_rows() -> None:
    stub = StubBackfill()
    stub.report = BackfillReport(stored=1)
    bus = TickBus(None)
    collector = Collector(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        FixedClock(MarketSettings()),
        StubUniverse(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        bus=bus,
        session_backfill=stub,  # type: ignore[arg-type]
        session_backfill_days=5,
    )
    through = date(2026, 9, 26)  # a trading day (Saturday, per trading_weekdays)
    reports = await collector.backfill_sessions(through)
    assert len(stub.days) == 5
    assert all(d.weekday() not in (3, 4) for d in stub.days)  # Thu/Fri skipped
    assert stub.days[0] == through
    assert len(reports) == 5


async def test_collector_backfill_sessions_disabled_by_default() -> None:
    collector = Collector(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        FixedClock(MarketSettings()),
        StubUniverse(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    assert await collector.backfill_sessions(date(2026, 9, 26)) == []
