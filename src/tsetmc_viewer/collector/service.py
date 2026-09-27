"""The collector: one cycle per minute, aligned to wall-clock minute boundaries.

A cycle:
1. resolve today's fund universe (cached; synced once per day)
2. fetch in parallel: market watch, client types, market overview, NAV per fund
3. store every raw response
4. parse → build ticks (``pipeline.cycle.process_cycle``)
5. validate and repair (``pipeline.validate.Validator``)
6. write ticks, quality issues and market tick, then the run record

Outside market hours the collector also keeps the database *useful*
(``bootstrap``): it catches up the official daily history and, when the last
session has no minute data (fresh install, or the collector was down), stores
one **closing snapshot** of that session, stamped at its close.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import zlib
from collections.abc import Awaitable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from tsetmc_viewer import telemetry
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.heartbeat import Heartbeat
from tsetmc_viewer.collector.leadership import Leadership
from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.domain.status import FundState
from tsetmc_viewer.pipeline.backfill import BackfillReport, IntradayBackfill, SessionBackfill
from tsetmc_viewer.pipeline.cycle import process_cycle
from tsetmc_viewer.pipeline.history import HistorySync
from tsetmc_viewer.pipeline.transform import FundTick, MarketTick
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseError
from tsetmc_viewer.pipeline.validate import QualityIssue, Validator
from tsetmc_viewer.sources.http import RawResponse, SourceError
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import (
    PayloadError,
    parse_market_overview,
    parse_market_watch,
)
from tsetmc_viewer.storage.repository import CollectionRun, RunStatus
from tsetmc_viewer.storage.tickbus import TickBus

log = logging.getLogger(__name__)

# Each fund's trading status is refreshed once per this many minutes (round robin).
STATUS_EVERY_MINUTES = 5


class RunSink(Protocol):
    """What the collector needs from storage (satisfied by ``Repository``)."""

    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int: ...
    async def insert_run(self, run: CollectionRun) -> None: ...
    async def insert_fund_ticks(self, ticks: Sequence[FundTick]) -> int: ...
    async def insert_market_tick(self, tick: MarketTick) -> None: ...
    async def insert_quality_issues(self, issues: Sequence[QualityIssue]) -> int: ...
    async def insert_fund_states(self, states: Sequence[FundState]) -> int: ...
    async def load_last_ticks(self, day: date) -> list[FundTick]: ...
    async def latest_history_date(self) -> date | None: ...
    async def record_market_day(
        self, day: date, *, trading: bool, note: str, at: datetime
    ) -> None: ...
    async def load_market_days(self) -> list[tuple[date, bool, str]]: ...


@dataclass(frozen=True, slots=True)
class BootstrapReport:
    session: date | None
    history_days: int  # 0 = history already up to date (or unavailable)
    snapshot: CollectionRun | None


class Collector:
    def __init__(
        self,
        tsetmc: TsetmcClient,
        repo: RunSink,
        clock: MarketClock,
        universe: FundUniverse,
        validator: Validator,
        history: HistorySync | None = None,
        history_days_after_close: int = 10,
        history_max_days: int = 400,
        bus: TickBus | None = None,
        heartbeat: Heartbeat | None = None,
        alert_after_failures: int = 3,
        leadership: Leadership | None = None,
        backfill: IntradayBackfill | None = None,
        session_backfill: SessionBackfill | None = None,
        session_backfill_days: int = 5,
    ) -> None:
        self._tsetmc = tsetmc
        self._repo = repo
        self._clock = clock
        self._universe = universe
        self._validator = validator
        self._history = history
        self._history_days = history_days_after_close
        self._history_max_days = history_max_days
        self._history_done: date | None = None
        self._bus = bus or TickBus(None)
        self._heartbeat = heartbeat
        self._leadership = leadership
        self._alert_after = alert_after_failures
        self.failed_streak = 0
        self._confirmed_day: date | None = None  # session guard: TSETMC shows today's trades
        self._holiday_checked: date | None = None
        self._backfill = backfill
        self._backfill_day: date | None = None  # the day the backfill ran (or is running)
        self._session_backfill = session_backfill
        self._session_backfill_days = session_backfill_days
        self._live_cycles: tuple[date | None, int] = (None, 0)  # successful cycles today
        self._background: set[asyncio.Task[None]] = set()
        self._closed_day: date | None = None  # the day whose close was committed
        self._states_day: date | None = None  # the day every fund's status was fetched

    async def collect_once(self, tick: datetime | None = None, note: str = "") -> CollectionRun:
        started = self._clock.now()
        tick = self._clock.floor_minute(tick or started)
        funds = await self._universe.get(tick.date())
        responses, errors, requests = await self._fetch(funds, self._status_targets(tick, funds))
        return await self._commit(tick, funds, responses, errors, requests, started, note)

    def _status_targets(self, tick: datetime, funds: Mapping[str, FundRef]) -> list[str]:
        """Funds whose trading status is fetched this cycle.

        Every fund on the first cycle of the day, then a fifth of them per minute, so
        each status is at most five minutes old for ~32 extra requests a minute. A
        status changes a few times a year per fund; a price halts within minutes.
        """
        if self._states_day != tick.date():
            self._states_day = tick.date()
            return list(funds)
        slot = tick.minute % STATUS_EVERY_MINUTES
        return [i for i in funds if zlib.crc32(i.encode()) % STATUS_EVERY_MINUTES == slot]

    async def _fetch(
        self, funds: Mapping[str, FundRef], status_for: Collection[str] = ()
    ) -> tuple[list[RawResponse], list[SourceError], int]:
        jobs: list[Awaitable[RawResponse]] = [
            self._tsetmc.market_watch(),
            self._tsetmc.client_type_all(),
            self._tsetmc.market_overview(),
            *(self._tsetmc.etf(ins) for ins in funds),
            *(self._tsetmc.closing_price_info(ins) for ins in status_for),
        ]
        results = await asyncio.gather(*jobs, return_exceptions=True)
        responses = [r for r in results if isinstance(r, RawResponse)]
        errors: list[SourceError] = []
        for r in results:
            if isinstance(r, BaseException):
                if not isinstance(r, SourceError):
                    raise r  # programming error: do not swallow
                errors.append(r)
        return responses, errors, len(jobs)

    async def _commit(
        self,
        tick: datetime,
        funds: Mapping[str, FundRef],
        responses: list[RawResponse],
        errors: list[SourceError],
        requests: int,
        started: datetime,
        note: str = "",
    ) -> CollectionRun:
        """Archive, parse, validate and write one cycle; announce it once committed."""
        run_id = uuid4()
        for err in errors:
            log.error("source error", extra={"run_id": str(run_id), "error": str(err)})
        await self._repo.insert_raw(run_id, responses)

        result = process_cycle(
            responses=responses,
            universe=funds,
            ts=tick,
            run_id=run_id,
            ingested_at=self._clock.now(),
        )
        if self._validator.day != tick.date():
            # First cycle of the day (or after a restart): resume from stored state.
            self._validator.warm(tick.date(), await self._repo.load_last_ticks(tick.date()))
        checked = self._validator.validate(
            result.batch, ts=tick, run_id=run_id, ingested_at=self._clock.now()
        )
        await self._repo.insert_fund_ticks(checked.ticks)
        await self._repo.insert_quality_issues(checked.issues)
        await self._repo.insert_fund_states(result.states)
        if result.market is not None:
            await self._repo.insert_market_tick(result.market)

        failed = len(errors) + sum(1 for r in responses if not r.ok)
        status: RunStatus
        if not result.batch.ticks:
            status = "failed"
        elif failed or result.batch.missing or result.errors:
            status = "partial"
        else:
            status = "ok"
        run = CollectionRun(
            run_id=run_id,
            started_at=started,
            finished_at=self._clock.now(),
            tick=tick,
            status=status,
            requests=requests,
            failed=failed,
            expected_funds=len(funds),
            received_funds=len(result.batch.ticks),
            issues=len(checked.issues),
            filled=checked.filled,
            repaired=checked.repaired,
            note="; ".join(filter(None, [note, *result.errors[:5]])),
        )
        await self._repo.insert_run(run)
        self._export(run, checked.issues)
        if checked.ticks:
            # Only after the rows are committed: caches keyed on this tick are now valid.
            await self._bus.publish(
                tick, {"status": status, "funds": run.received_funds, "run_id": str(run_id)}
            )
        log.info(
            "cycle finished",
            extra={
                "run_id": str(run_id),
                "tick": str(tick),
                "status": status,
                "funds": f"{run.received_funds}/{run.expected_funds}",
                "failed_requests": failed,
                "issues": len(checked.issues),
                "filled": checked.filled,
                "seconds": round((run.finished_at - started).total_seconds(), 2),
                **({"note": note} if note else {}),
            },
        )
        return run

    # --- off-hours: keep the database useful ---------------------------------------------
    async def last_session(self) -> date | None:
        """The trading day whose figures TSETMC is currently showing (one small request)."""
        raw = await self._tsetmc.market_overview()
        if not raw.ok:
            raise SourceError(f"market overview HTTP {raw.status_code}")
        try:
            overview = parse_market_overview(raw.json())
        except (ValueError, PayloadError) as exc:
            raise SourceError(f"market overview unreadable: {exc}") from exc
        d = overview.deven
        if d <= 0:
            return None
        y, md = divmod(d, 10000)
        return date(y, *divmod(md, 100))

    async def catch_up_history(self, session: date) -> int:
        """Load official daily history up to ``session``; return the days requested (0 = none).

        Empty table → the full window (``history_max_days``); otherwise just the gap,
        but never less than the usual after-close refresh (recent days get corrected).
        """
        if self._history is None:
            return 0
        latest = await self._repo.latest_history_date()
        if latest is not None and latest >= session:
            return 0
        if latest is None:
            days = self._history_max_days
        else:
            gap = (session - latest).days  # calendar days ≥ trading days missing
            days = min(self._history_max_days, max(self._history_days, gap + 5))
        funds = await self._universe.get(self._clock.now().date())
        await self._history.sync(funds.values(), days=days)
        return days

    async def closing_snapshot(
        self, session: date, *, refresh: bool = False
    ) -> CollectionRun | None:
        """Store the final state of ``session`` if it has no minute data at all.

        ``refresh`` (after every close): store it even if the day has minute data, so
        the close-stamped tick carries TSETMC's official closing figures.

        After the close TSETMC keeps serving the session's final figures, so one
        ordinary cycle, stamped at the close, gives the panel a complete end-of-day
        picture. Skipped while trading (the live loop owns that) and when TSETMC
        already shows the next day with no trades yet (pre-open reset).
        """
        now = self._clock.now()
        if self._clock.is_open(now) or (not refresh and await self._repo.load_last_ticks(session)):
            return None
        funds = await self._universe.get(now.date())
        responses, errors, requests = await self._fetch(funds)
        if not _has_trades(responses, funds):
            log.warning(
                "closing snapshot skipped: no trades in the feed", extra={"session": str(session)}
            )
            return None
        tick = self._clock.session_close(session)
        return await self._commit(
            tick, funds, responses, errors, requests, now, note="closing snapshot"
        )

    async def bootstrap(self) -> BootstrapReport:
        """Make a fresh (or long-stopped) install show the last session right away."""
        if self._clock.is_open(self._clock.now()):
            return BootstrapReport(None, 0, None)  # live cycles start now; history after close
        try:
            session = await self.last_session()
            if session is None:
                return BootstrapReport(None, 0, None)
            days = await self.catch_up_history(session)
            snapshot = await self.closing_snapshot(session)
            await self.backfill_sessions(session)
        except (SourceError, UniverseError) as exc:
            log.warning(
                "bootstrap failed; will retry after the next close", extra={"error": str(exc)}
            )
            return BootstrapReport(None, 0, None)
        log.info(
            "bootstrap done",
            extra={
                "session": str(session),
                "history_days": days,
                "snapshot": snapshot.status if snapshot else "not needed",
            },
        )
        return BootstrapReport(session, days, snapshot)

    async def backfill_sessions(self, through: date) -> list[BackfillReport]:
        """Rebuild minute data for the recent trading days the collector never ran during.

        Runs once at boot, for the ``session_backfill_days`` trading days up to and
        including ``through`` (weekends/holidays skipped). Idempotent per fund per day
        (``backfilled_funds``), so a partial or interrupted run resumes where it left off
        on the next boot instead of redoing work (ADR 0013).
        """
        if self._session_backfill is None or self._session_backfill_days <= 0:
            return []
        funds = await self._universe.get(self._clock.now().date())
        targets: list[date] = []
        day = through
        while len(targets) < self._session_backfill_days:
            if self._clock.is_trading_day(datetime.combine(day, time(12), tzinfo=self._clock.tz)):
                targets.append(day)
            day -= timedelta(days=1)
        reports: list[BackfillReport] = []
        for d in targets:
            try:
                reports.append(await self._session_backfill.run(d, funds))
            except (SourceError, UniverseError) as exc:
                log.warning("session backfill failed", extra={"day": str(d), "error": str(exc)})
        total = sum(r.stored for r in reports)
        if total:
            await self._bus.bump("session-backfill")
        log.info(
            "session backfill batch done",
            extra={"days": len(targets), "funds_stored": total},
        )
        return reports

    async def _prepare_day(self, now: datetime) -> None:
        """Before the open on a trading day, sync the fund universe once."""
        if not self._clock.is_trading_day(now):
            return
        try:
            await self._universe.get(now.date())
        except (SourceError, UniverseError) as exc:
            log.warning("pre-open universe sync failed", extra={"error": str(exc)})

    async def _after_close(self, now: datetime) -> None:
        """Once per trading day after the close: official history (+ snapshot if we missed it)."""
        if (
            self._history_done == now.date()
            or not self._clock.is_trading_day(now)
            or not self._clock.is_after_close(now)
        ):
            return
        try:
            await self.catch_up_history(now.date())
            await self.closing_snapshot(now.date(), refresh=True)
            self._history_done = now.date()
        except (SourceError, UniverseError) as exc:
            log.warning("after-close sync failed", extra={"error": str(exc)})
        if self._backfill_day != now.date():
            # Never ran during the session (started after the close, or too late for three
            # live cycles): the closing snapshot is then the live point to check against.
            await self.backfill_intraday(now.date())

    async def _close_session(self, now: datetime) -> None:
        """Right after the close, commit the session's final state stamped at the close.

        The last in-session cycle is at close − 1 min; without this the panel's last
        point stayed at 12:29 and no tick told open panels that trading had ended.
        ``_after_close`` refreshes the same stamp with the official figures later.
        """
        day = now.date()
        seen_day, count = self._live_cycles
        if self._closed_day == day or seen_day != day or not count:
            return
        close = self._clock.session_close(day)
        if now < close:
            return
        self._closed_day = day
        try:
            await self.collect_once(close, note="session close")
        except Exception:
            log.exception("session close cycle failed")  # the refresh after close retries

    async def backfill_intraday(self, day: date) -> BackfillReport | None:
        """Rebuild the minutes of ``day`` missed before the collector started (ADR 0012)."""
        if self._backfill is None:
            return None
        self._backfill_day = day
        try:
            report = await self._backfill.run(day, await self._universe.get(day))
            if report.minutes:
                # New rows under an unchanged tick: bump it, or cached pages and open
                # panels keep showing the gap until the next session.
                await self._bus.bump("backfill")
            return report
        except (SourceError, UniverseError) as exc:
            self._backfill_day = None  # try again later today
            log.warning("intraday backfill failed", extra={"error": str(exc)})
        except Exception:
            # Often runs as a background task: nothing above would ever see this. Not
            # retried today, so a persistent bug does not hammer TSETMC every minute.
            log.exception("intraday backfill crashed")
        return None

    async def _backfill_quietly(self, day: date) -> None:
        await self.backfill_intraday(day)

    def _after_cycle(self, run: CollectionRun) -> None:
        """After the third successful cycle of the day, backfill in the background.

        Three live ticks give the check something to compare with; running it in a task
        keeps the minute loop on schedule (the fetch takes ~10 s for all funds).
        """
        day = run.tick.date()
        seen_day, count = self._live_cycles
        count = (count if seen_day == day else 0) + (run.status != "failed")
        self._live_cycles = (day, count)
        if self._backfill is None or self._backfill_day == day or count < 3:
            return
        self._backfill_day = day  # claim it now: the task starts on the next loop turn
        task = asyncio.create_task(self._backfill_quietly(day))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def run_forever(
        self,
        interval_seconds: int,
        *,
        ignore_market_hours: bool,
        bootstrap: bool = True,
        stop: asyncio.Event | None = None,
    ) -> None:
        """Collect every ``interval_seconds`` while the market is open, until ``stop`` is set.

        Stopping is graceful: a cycle in progress is finished (its rows and run record
        written) and only the sleep between cycles is cut short.
        """
        stop = stop or asyncio.Event()
        await self._load_calendar()
        renewer = asyncio.create_task(self._leadership.keep(stop)) if self._leadership else None
        try:
            await self._loop(interval_seconds, ignore_market_hours, bootstrap, stop)
        finally:
            stop.set()
            if renewer is not None:
                await renewer  # releases the lease: a standby takes over at once
        log.info("collector stopped")

    async def _loop(
        self, interval_seconds: int, ignore_market_hours: bool, bootstrap: bool, stop: asyncio.Event
    ) -> None:
        bootstrapped = not bootstrap
        while not stop.is_set():
            if self._leadership is not None and not await self._is_leader():
                self._beat("standby", 60)
                await _sleep(15, stop)
                continue
            if not bootstrapped:
                self._beat("bootstrapping", 900)
                await self.bootstrap()
                bootstrapped = True
            now = self._clock.now()
            telemetry.MARKET_OPEN.set(int(self._clock.is_open(now)))
            telemetry.SESSION_CONFIRMED.set(int(self._confirmed_day == now.date()))
            if not ignore_market_hours and not self._clock.is_open(now):
                await self._close_session(now)
                await self._prepare_day(now)
                await self._after_close(now)
                await self._check_listed_holiday(now)
                if self._clock.is_open(now):
                    continue  # the holiday list was wrong: the market is trading
                wait = (self._clock.next_open(now) - now).total_seconds()
                # Wake up at least every 30 min to retry a failed pre-open sync, and at
                # open + guard on a listed holiday to verify the market really is shut.
                wait = max(1.0, min(wait, 1800, self._until_holiday_check(now)))
                log.info("market closed, sleeping", extra={"seconds": int(wait)})
                self._beat("sleeping", wait)
                await _sleep(wait, stop)
                continue

            self._beat("collecting", interval_seconds)
            if ignore_market_hours or await self._session_confirmed(now):
                try:
                    run = await self.collect_once(now)
                    self._record(run.status != "failed")
                    self._after_cycle(run)
                except Exception:
                    # The loop must survive any single bad cycle (DB hiccup, etc.).
                    log.exception("cycle crashed")
                    self._record(False)
            await _sleep(
                self._clock.seconds_until_next_tick(self._clock.now(), interval_seconds), stop
            )

    async def _is_leader(self) -> bool:
        assert self._leadership is not None
        # The background task renews; until its first answer, ask once ourselves.
        return self._leadership.is_leader or await self._leadership.check()

    # --- trading calendar: session guard ----------------------------------------------------
    async def _load_calendar(self) -> None:
        try:
            self._clock.calendar.load_observed(await self._repo.load_market_days())
        except Exception:
            log.exception("could not load observed market days")

    async def _session_confirmed(self, now: datetime) -> bool:
        """Is TSETMC actually trading today? Checked with one small request per minute
        until the first trade shows up; no trade by open + guard = unannounced closure."""
        today = now.date()
        if self._confirmed_day == today:
            return True
        try:
            session = await self.last_session()
        except SourceError as exc:
            # Cannot tell: collect anyway, so the failure shows up in runs and alerts.
            log.warning("session check failed", extra={"error": str(exc)})
            return True
        if session == today:
            self._confirmed_day = today
            log.info("session confirmed", extra={"day": str(today)})
            return True
        if now >= self._clock.session_open(today) + self._clock.session_guard:
            note = "تعطیلی اعلام‌نشده: بازار در این روز معامله‌ای نداشت"
            self._clock.calendar.observe(today, trading=False, note=note)
            await self._repo.record_market_day(today, trading=False, note=note, at=now)
            log.warning(
                "market did not open today; recorded as a closure",
                extra={"day": str(today), "tsetmc_session": str(session)},
            )
        else:
            log.info("waiting for the first trade of the day", extra={"day": str(today)})
        return False

    async def _check_listed_holiday(self, now: datetime) -> None:
        """On a listed holiday, verify once (after open + guard) that TSETMC is really shut."""
        today = now.date()
        holiday = self._clock.holiday(now)
        start = self._clock.session_open(today) + self._clock.session_guard
        if (
            holiday is None
            or self._holiday_checked == today
            or not (start <= now <= self._clock.session_close(today))
        ):
            return
        self._holiday_checked = today
        try:
            session = await self.last_session()
        except SourceError as exc:
            log.warning("holiday check failed", extra={"error": str(exc)})
            return
        if session == today:
            note = f"فهرست تعطیلات اشتباه بود ({holiday}): بازار باز بود"
            self._clock.calendar.observe(today, trading=True, note=note)
            await self._repo.record_market_day(today, trading=True, note=note, at=now)
            self._confirmed_day = today
            log.error("listed holiday but the market is trading", extra={"holiday": holiday})

    def _until_holiday_check(self, now: datetime) -> float:
        """Seconds until open + guard on a listed holiday (else no limit)."""
        if self._clock.holiday(now) is None or self._holiday_checked == now.date():
            return float("inf")
        start = self._clock.session_open(now.date()) + self._clock.session_guard
        # Before the window: wake at its start. Inside it the check has just run; after it, none.
        return max(1.0, (start - now).total_seconds()) if now < start else float("inf")

    # --- health ---------------------------------------------------------------------------
    @staticmethod
    def _export(run: CollectionRun, issues: Sequence[QualityIssue]) -> None:
        """Prometheus view of one cycle (docs/11-monitoring.md)."""
        telemetry.CYCLES.labels(run.status).inc()
        telemetry.CYCLE_SECONDS.observe((run.finished_at - run.started_at).total_seconds())
        telemetry.FUNDS_EXPECTED.set(run.expected_funds)
        telemetry.FUNDS_RECEIVED.set(run.received_funds)
        if run.status != "failed":
            telemetry.LAST_SUCCESS.set(run.finished_at.timestamp())
        telemetry.ROWS_REPAIRED.labels("forward_filled").inc(run.filled)
        telemetry.ROWS_REPAIRED.labels("repaired").inc(run.repaired)
        for issue in issues:
            telemetry.QUALITY_ISSUES.labels(str(issue.check), issue.action).inc()

    def _record(self, ok: bool) -> None:
        """Edge-triggered alerting on consecutive failed cycles (one ERROR, one recovery)."""
        if ok:
            if self.failed_streak >= self._alert_after:
                log.info("collector recovered", extra={"failed_cycles": self.failed_streak})
            self.failed_streak = 0
            telemetry.FAILED_STREAK.set(0)
            return
        self.failed_streak += 1
        telemetry.FAILED_STREAK.set(self.failed_streak)
        if self.failed_streak == self._alert_after:
            log.error(
                "collector failing",
                extra={
                    "failed_cycles": self.failed_streak,
                    "hint": "TSETMC unreachable? (VPN on / IP blocked) or ClickHouse down",
                },
            )

    def _beat(self, state: str, expected_seconds: float) -> None:
        """Write the heartbeat: the loop promises to beat again before ``deadline``."""
        if self._heartbeat is None:
            return
        now = self._clock.now()
        self._heartbeat.write(
            {
                "state": state,
                "at": now.isoformat(),
                "deadline": (now + timedelta(seconds=expected_seconds + 120)).isoformat(),
                "failed_streak": self.failed_streak,
            }
        )


async def _sleep(seconds: float, stop: asyncio.Event) -> None:
    """Sleep, but wake immediately when ``stop`` is set."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


def _has_trades(responses: Sequence[RawResponse], funds: Mapping[str, FundRef]) -> bool:
    """Did any fund trade in the session the feed shows? (False right after a pre-open reset.)"""
    for r in responses:
        if r.endpoint == "market_watch" and r.ok:
            try:
                rows = parse_market_watch(r.json())
            except (ValueError, PayloadError):
                return False
            return any(row.ins_code in funds and row.trade_count > 0 for row in rows)
    return False
