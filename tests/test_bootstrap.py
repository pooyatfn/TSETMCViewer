"""Off-hours bootstrap: a fresh install must show the last session, not an empty panel."""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

import pytest
import respx

from support import BASE, EQUITY_SAMPLES, TEHRAN, MemoryStore, fixture, mock_tsetmc
from tsetmc_viewer.analytics.service import AnalyticsService
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.pipeline.history import HistorySync
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.migrate import migrate
from tsetmc_viewer.storage.repository import Repository

SESSION = date(2026, 9, 23)  # marketActivityDEven of the recorded market overview (Wednesday)
THURSDAY = datetime(2026, 9, 24, 10, 0, tzinfo=TEHRAN)  # weekend: market closed all day


class FixedClock(MarketClock):
    def __init__(self, settings: MarketSettings, now: datetime) -> None:
        super().__init__(settings)
        self._now = now

    def now(self) -> datetime:
        return self._now


def make(client: TsetmcClient, store: Any, now: datetime) -> Collector:
    clock = FixedClock(MarketSettings(), now)
    universe = FundUniverse(UniverseSync(client, store, clock), store)
    return Collector(
        client,
        store,
        clock,
        universe,
        Validator(ValidationSettings(), clock),
        history=HistorySync(client, store, clock),
    )


async def test_fresh_install_gets_history_and_a_closing_snapshot(
    http_settings: HttpSettings,
) -> None:
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, THURSDAY)
            report = await collector.bootstrap()
            again = await collector.bootstrap()

    assert report.session == SESSION
    assert report.history_days == 400  # empty table → the full window
    assert max(r.trade_date for r in store.history) == SESSION
    snap = report.snapshot
    assert snap is not None
    assert snap.status == "ok"
    assert "closing snapshot" in snap.note
    # Stamped at the session's close, not at "now" (a Thursday with no trading).
    assert snap.tick == datetime(2026, 9, 23, 12, 30, tzinfo=TEHRAN)
    assert {t.ins_code for t in store.ticks} == EQUITY_SAMPLES
    assert {t.ts for t in store.ticks} == {snap.tick}
    # Idempotent: a restart neither reloads history nor writes a second snapshot.
    assert (again.history_days, again.snapshot) == (0, None)
    assert len(store.runs) == 1


async def test_does_nothing_while_the_market_is_open(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            report = await make(
                client, store, datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)
            ).bootstrap()
            calls = router.calls.call_count
    assert (report.session, report.snapshot) == (None, None)
    assert calls == 0  # the live loop owns trading hours
    assert not store.ticks


async def test_skips_the_snapshot_after_a_pre_open_reset(http_settings: HttpSettings) -> None:
    watch = copy.deepcopy(fixture("market_watch.json"))
    for row in watch["marketwatch"]:
        row["ztt"] = 0  # TSETMC already shows the new day, nothing traded yet
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router, market_watch=watch)
        async with TsetmcClient(BASE, http_settings) as client:
            report = await make(client, store, THURSDAY).bootstrap()
    assert report.snapshot is None
    assert not store.ticks


async def test_history_catch_up_requests_only_the_gap(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, THURSDAY)
            await collector.catch_up_history(date(2026, 9, 10))  # seeds history up to 09-23
            store.history = [r for r in store.history if r.trade_date <= date(2026, 9, 10)]
            latest = await store.latest_history_date()
            days = await collector.catch_up_history(SESSION)
    assert latest is not None
    # calendar gap + margin, not the full 400-day window
    assert days == (SESSION - latest).days + 5


@pytest.mark.integration
async def test_bootstrapped_database_feeds_the_panel(
    ch_client: Any, http_settings: HttpSettings
) -> None:
    """End to end on ClickHouse: after bootstrap the API serves the last session."""
    await migrate(ch_client)
    repo = Repository(ch_client)
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            await make(client, repo, THURSDAY).bootstrap()

    assert await repo.latest_history_date() == SESSION
    analytics = AnalyticsService(ch_client, FixedClock(MarketSettings(), THURSDAY))
    assert await analytics.session_date() == SESSION
    overview = await analytics.overview(SESSION)
    assert overview.funds == len(EQUITY_SAMPLES)
    # Units were synced "today" (Thursday), after the session: still used for net assets.
    assert overview.total_aum > 0
    assert overview.is_live is False
    assert overview.index_value is not None
    assert await analytics.returns(SESSION)
