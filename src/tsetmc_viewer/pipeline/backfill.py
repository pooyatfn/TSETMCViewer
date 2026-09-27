"""Rebuild today's minutes that were missed because the collector started late.

TSETMC keeps every trade of the current day (``Trade/GetTrade``). Summing them
gives, for any moment, what the market watch would have shown for price,
volume, value and trade count. It does **not** give individual/institutional
flows, NAV or the order book, so only those four fields are rebuilt, and they
go to their own table (``fund_ticks_backfill``) instead of ``fund_ticks``:
analytics that read flows or NAV can never see a reconstructed row.

Trust, then store. The real probe run found trade times bunched after 12:00
for 6 of 40 funds, so a fund's rebuilt series is only stored if it agrees with
the live ticks the collector already wrote today (ADR 0012):

    live tick stamped ts is fetched during [ts, ts+60s), and the feed itself may
    lag, so its volume must lie within [cum(ts − 60s), cum(ts + 60s)]

A fund passes when at least ``min_match`` of its live minutes agree. Only
minutes before its first live tick are stored; live data is never replaced.
"""

from __future__ import annotations

import asyncio
import bisect
import itertools
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta
from typing import Literal, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from tsetmc_viewer import telemetry
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.sources.http import RawResponse, SourceError
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import (
    PayloadError,
    PriceHistoryRow,
    TradeRow,
    parse_price_history,
    parse_trades,
)

log = logging.getLogger(__name__)

TEHRAN = ZoneInfo("Asia/Tehran")
MINUTE = 60
Status = Literal["stored", "rejected", "no_trades", "no_gap", "error"]


def seconds_of_day(moment: datetime | time) -> int:
    """Tehran wall-clock seconds since midnight (naive values are taken as Tehran)."""
    if isinstance(moment, datetime) and moment.tzinfo is not None:
        moment = moment.astimezone(TEHRAN)
    return moment.hour * 3600 + moment.minute * 60 + moment.second


def heven_seconds(heven: int) -> int:
    h, rem = divmod(heven, 10000)
    m, s = divmod(rem, 100)
    return h * 3600 + m * 60 + s


@dataclass(frozen=True, slots=True)
class State:
    """What the market watch would show at a moment: last price and running totals."""

    last_price: int
    volume: int
    value: int
    trades: int


class Tape:
    """One instrument's trades of the day, queryable at any second."""

    def __init__(self, rows: Sequence[TradeRow]) -> None:
        kept = sorted(
            ((heven_seconds(r.heven), r.n, r) for r in rows if not r.canceled),
            key=lambda x: (x[0], x[1]),
        )
        self._times = [t for t, _, _ in kept]
        self._prices = [r.price for _, _, r in kept]
        self._volume = list(itertools.accumulate(r.volume for _, _, r in kept))
        self._value = list(itertools.accumulate(r.volume * r.price for _, _, r in kept))

    def __len__(self) -> int:
        return len(self._times)

    @property
    def first(self) -> int | None:
        return self._times[0] if self._times else None

    def at(self, sod: int) -> State | None:
        """State after every trade stamped at or before ``sod``; None before the first trade."""
        k = bisect.bisect_right(self._times, sod)
        if k == 0:
            return None
        return State(self._prices[k - 1], self._volume[k - 1], self._value[k - 1], k)

    def volume_at(self, sod: int) -> int:
        state = self.at(sod)
        return state.volume if state else 0


@dataclass(frozen=True, slots=True)
class Verdict:
    overlap: int  # live minutes compared
    matched: int

    def passes(self, min_match: float) -> bool:
        return self.overlap > 0 and self.matched >= min_match * self.overlap


def verify(tape: Tape, live: Sequence[tuple[int, int]], tolerance: float = 0.01) -> Verdict:
    """Compare the tape with live ``(seconds_of_day, volume)`` snapshots of the same fund."""
    matched = 0
    for sod, volume in live:
        low = tape.volume_at(sod - MINUTE) * (1 - tolerance)
        high = tape.volume_at(sod + MINUTE) * (1 + tolerance)
        matched += low - 1 <= volume <= high + 1
    return Verdict(len(live), matched)


def missing_minutes(tape: Tape, open_sod: int, first_live_sod: int) -> list[tuple[int, State]]:
    """Minute boundaries from the open up to (not including) the first live tick."""
    out: list[tuple[int, State]] = []
    for sod in range(open_sod, first_live_sod, MINUTE):
        state = tape.at(sod)
        if state is not None:  # nothing to draw before the first trade
            out.append((sod, state))
    return out


@dataclass(frozen=True, slots=True)
class BackfillTick:
    """One row of ``fund_ticks_backfill``. Field order == insert column order."""

    ts: datetime
    ins_code: str
    last_price: int
    volume: int
    value: int
    trade_count: int
    ingested_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, c) for c in self.columns()]


@dataclass(frozen=True, slots=True)
class BackfillLog:
    """One row of ``intraday_backfill_log``: the decision for one fund and day."""

    day: date
    ins_code: str
    status: Status
    overlap: int
    matched: int
    minutes: int
    note: str
    recorded_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, c) for c in self.columns()]


@dataclass(frozen=True, slots=True)
class BackfillReport:
    funds: int = 0  # funds with a gap before their first live tick
    stored: int = 0
    rejected: int = 0  # the trades did not match the live ticks: nothing stored
    errors: int = 0  # retried on the next run
    minutes: int = 0
    rejected_symbols: tuple[str, ...] = ()


class BackfillStore(Protocol):
    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int: ...
    async def load_live_volumes(self, day: date) -> dict[str, list[tuple[datetime, int]]]: ...
    async def backfilled_funds(self, day: date) -> set[str]: ...
    async def insert_backfill(self, ticks: Sequence[BackfillTick]) -> int: ...
    async def insert_backfill_log(self, rows: Sequence[BackfillLog]) -> int: ...
    async def load_history_day(self, day: date) -> dict[str, tuple[int, int, int]]: ...


class IntradayBackfill:
    def __init__(
        self,
        tsetmc: TsetmcClient,
        store: BackfillStore,
        clock: MarketClock,
        *,
        tolerance: float = 0.01,
        min_match: float = 0.9,
    ) -> None:
        self._tsetmc = tsetmc
        self._store = store
        self._clock = clock
        self._tolerance = tolerance
        self._min_match = min_match

    async def run(self, day: date, funds: Mapping[str, FundRef]) -> BackfillReport:
        """Rebuild the missed minutes of ``day`` for every fund that needs it (idempotent)."""
        if day != self._clock.now().date():
            return BackfillReport()  # GetTrade only knows today
        live = await self._store.load_live_volumes(day)
        done = await self._store.backfilled_funds(day)
        open_sod = seconds_of_day(self._clock.session_open(day))
        todo: dict[str, list[tuple[int, int]]] = {}
        for ins in funds:
            points = [(seconds_of_day(ts), v) for ts, v in live.get(ins, [])]
            if ins in done or not points:
                continue
            if min(s for s, _ in points) > open_sod + MINUTE:  # there is a gap to fill
                todo[ins] = points
        if not todo:
            return BackfillReport()

        run_id = uuid4()
        results = await asyncio.gather(
            *(self._tsetmc.trades(ins) for ins in todo), return_exceptions=True
        )
        await self._store.insert_raw(run_id, [r for r in results if isinstance(r, RawResponse)])

        now = self._clock.now()
        ticks: list[BackfillTick] = []
        logs: list[BackfillLog] = []
        for (ins, points), result in zip(todo.items(), results, strict=True):
            decision = self._decide(day, ins, points, result, open_sod, now)
            logs.append(decision[0])
            ticks.extend(decision[1])
            telemetry.BACKFILL_FUNDS.labels(decision[0].status).inc()
        await self._store.insert_backfill(ticks)
        await self._store.insert_backfill_log(logs)
        rejected = [funds[r.ins_code].symbol for r in logs if r.status == "rejected"]
        report = BackfillReport(
            funds=len(todo),
            stored=sum(r.status == "stored" for r in logs),
            rejected=len(rejected),
            errors=sum(r.status == "error" for r in logs),
            minutes=len(ticks),
            rejected_symbols=tuple(rejected),
        )
        log.info(
            "intraday backfill done",
            extra={
                "day": str(day),
                "funds": report.funds,
                "stored": report.stored,
                "rejected": report.rejected,
                "errors": report.errors,
                "minutes": report.minutes,
                "rejected_symbols": ",".join(report.rejected_symbols),
            },
        )
        return report

    def _decide(
        self,
        day: date,
        ins: str,
        live: list[tuple[int, int]],
        result: RawResponse | BaseException,
        open_sod: int,
        now: datetime,
    ) -> tuple[BackfillLog, list[BackfillTick]]:
        def entry(
            status: Status, verdict: Verdict | None = None, minutes: int = 0, note: str = ""
        ) -> BackfillLog:
            v = verdict or Verdict(0, 0)
            return BackfillLog(day, ins, status, v.overlap, v.matched, minutes, note, now)

        if isinstance(result, BaseException):
            if not isinstance(result, SourceError):
                raise result
            return entry("error", note=str(result)), []
        if not result.ok:
            return entry("error", note=f"HTTP {result.status_code}"), []
        try:
            tape = Tape(parse_trades(result.json()))
        except (PayloadError, ValueError) as exc:
            return entry("error", note=f"bad payload: {exc}"), []
        if not tape:
            return entry("no_trades"), []

        verdict = verify(tape, live, self._tolerance)
        if not verdict.passes(self._min_match):
            first = tape.first or 0
            note = f"first trade {first // 3600:02d}:{first % 3600 // 60:02d}"
            log.warning(
                "backfill rejected",
                extra={"ins_code": ins, "overlap": verdict.overlap, "matched": verdict.matched},
            )
            return entry("rejected", verdict, note=note), []

        first_live = min(s for s, _ in live)
        midnight = datetime.combine(day, time(0), tzinfo=TEHRAN)
        ticks = [
            BackfillTick(
                ts=midnight + timedelta(seconds=sod),
                ins_code=ins,
                last_price=s.last_price,
                volume=s.volume,
                value=s.value,
                trade_count=s.trades,
                ingested_at=now,
            )
            for sod, s in missing_minutes(tape, open_sod, first_live - first_live % MINUTE)
        ]
        return entry("stored", verdict, minutes=len(ticks)), ticks


# --- past sessions (no live ticks to check against) -----------------------------------


class HistoryTape:
    """One instrument's price-change events of a **past** day; already cumulative.

    Unlike ``Tape`` (built from individual trades), each ``PriceHistoryRow`` already
    *is* the running total as of that moment, so no accumulation step is needed here.
    """

    def __init__(self, rows: Sequence[PriceHistoryRow]) -> None:
        kept = sorted(rows, key=lambda r: heven_seconds(r.heven))
        self._times = [heven_seconds(r.heven) for r in kept]
        self._states = [State(r.last_price, r.volume, r.value, r.trade_count) for r in kept]

    def __len__(self) -> int:
        return len(self._times)

    @property
    def last(self) -> State | None:
        return self._states[-1] if self._states else None

    def at(self, sod: int) -> State | None:
        k = bisect.bisect_right(self._times, sod)
        return self._states[k - 1] if k else None


def verify_official(
    tape: HistoryTape, official: tuple[int, int, int] | None, tolerance: float = 0.01
) -> Verdict:
    """Check the tape's final totals against TSETMC's own official daily rollup.

    There are no live ticks for a past day, so this is the only trust check available:
    one comparison (``Verdict(overlap=1, ...)``), not one per minute.
    """
    last = tape.last
    if last is None or official is None:
        return Verdict(0, 0)
    ov, oval, _otc = official
    volume_ok = bool(ov) and abs(last.volume - ov) <= tolerance * ov
    value_ok = abs(last.value - oval) <= tolerance * max(oval, 1)
    return Verdict(1, int(volume_ok and value_ok))


class SessionBackfill:
    """Rebuild a **past** trading day's minutes from price-change events (ADR 0013).

    Same table and trust-then-store philosophy as ``IntradayBackfill``, but for a
    session the collector never ran during: ``ClosingPrice/GetClosingPriceHistory``
    replaces ``Trade/GetTrade`` (which only ever answers for *today*, confirmed by
    probing both with a real past date — docs/02-data-sources.md), and the check is
    against the official end-of-day rollup instead of live ticks, since there is
    nothing live to compare with. Same field limitation as the same-day backfill:
    price/volume/value/trade_count only — no NAV, no individual/institutional flow.
    """

    def __init__(
        self,
        tsetmc: TsetmcClient,
        store: BackfillStore,
        clock: MarketClock,
        *,
        tolerance: float = 0.01,
    ) -> None:
        self._tsetmc = tsetmc
        self._store = store
        self._clock = clock
        self._tolerance = tolerance

    async def run(self, day: date, funds: Mapping[str, FundRef]) -> BackfillReport:
        """Rebuild ``day`` for every fund not already decided (idempotent, retries errors)."""
        if day >= self._clock.now().date():
            return BackfillReport()  # today (and later) is IntradayBackfill's job
        done = await self._store.backfilled_funds(day)
        official = await self._store.load_history_day(day)
        todo = [ins for ins in funds if ins not in done]
        if not todo:
            return BackfillReport()

        run_id = uuid4()
        date_str = day.strftime("%Y%m%d")
        results = await asyncio.gather(
            *(self._tsetmc.price_history(ins, date_str) for ins in todo), return_exceptions=True
        )
        await self._store.insert_raw(run_id, [r for r in results if isinstance(r, RawResponse)])

        open_sod = seconds_of_day(self._clock.session_open(day))
        close_sod = seconds_of_day(self._clock.session_close(day))
        now = self._clock.now()
        ticks: list[BackfillTick] = []
        logs: list[BackfillLog] = []
        for ins, result in zip(todo, results, strict=True):
            decision = self._decide(day, ins, official.get(ins), result, open_sod, close_sod, now)
            logs.append(decision[0])
            ticks.extend(decision[1])
            telemetry.BACKFILL_FUNDS.labels(decision[0].status).inc()
        await self._store.insert_backfill(ticks)
        await self._store.insert_backfill_log(logs)
        rejected = [funds[r.ins_code].symbol for r in logs if r.status == "rejected"]
        report = BackfillReport(
            funds=len(todo),
            stored=sum(r.status == "stored" for r in logs),
            rejected=len(rejected),
            errors=sum(r.status == "error" for r in logs),
            minutes=len(ticks),
            rejected_symbols=tuple(rejected),
        )
        log.info(
            "session backfill done",
            extra={
                "day": str(day),
                "funds": report.funds,
                "stored": report.stored,
                "rejected": report.rejected,
                "errors": report.errors,
                "minutes": report.minutes,
            },
        )
        return report

    def _decide(
        self,
        day: date,
        ins: str,
        official: tuple[int, int, int] | None,
        result: RawResponse | BaseException,
        open_sod: int,
        close_sod: int,
        now: datetime,
    ) -> tuple[BackfillLog, list[BackfillTick]]:
        def entry(
            status: Status, verdict: Verdict | None = None, minutes: int = 0, note: str = ""
        ) -> BackfillLog:
            v = verdict or Verdict(0, 0)
            return BackfillLog(day, ins, status, v.overlap, v.matched, minutes, note, now)

        if isinstance(result, BaseException):
            if not isinstance(result, SourceError):
                raise result
            return entry("error", note=str(result)), []
        if not result.ok:
            return entry("error", note=f"HTTP {result.status_code}"), []
        try:
            tape = HistoryTape(parse_price_history(result.json()))
        except (PayloadError, ValueError) as exc:
            return entry("error", note=f"bad payload: {exc}"), []
        if not tape:
            return entry("no_trades"), []

        verdict = verify_official(tape, official, self._tolerance)
        if not verdict.passes(1.0):
            note = "no official daily row" if official is None else "mismatch vs official EOD"
            log.warning("session backfill rejected", extra={"ins_code": ins, "day": str(day)})
            return entry("rejected", verdict, note=note), []

        midnight = datetime.combine(day, time(0), tzinfo=TEHRAN)
        ticks = [
            BackfillTick(
                ts=midnight + timedelta(seconds=sod),
                ins_code=ins,
                last_price=s.last_price,
                volume=s.volume,
                value=s.value,
                trade_count=s.trades,
                ingested_at=now,
            )
            for sod in range(open_sod, close_sod + 1, MINUTE)
            if (s := tape.at(sod)) is not None
        ]
        return entry("stored", verdict, minutes=len(ticks)), ticks
