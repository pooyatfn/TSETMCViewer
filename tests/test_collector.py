from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import pytest
import respx

from support import ATLAS, BASE, EQUITY_SAMPLES, TEHRAN, MemoryStore, fixture, mock_tsetmc
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.pipeline.replay import replay_day
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.migrate import migrate
from tsetmc_viewer.storage.repository import Repository, quality_report

TICK = datetime(2026, 9, 26, 10, 0, 30, tzinfo=TEHRAN)


def make_collector(client: TsetmcClient, store: Any, settings: MarketSettings) -> Collector:
    clock = MarketClock(settings)
    universe = FundUniverse(UniverseSync(client, store, clock), store)
    return Collector(client, store, clock, universe, Validator(ValidationSettings(), clock))


async def test_full_cycle_from_recorded_responses(
    http_settings: HttpSettings, market_settings: MarketSettings
) -> None:
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            run = await make_collector(client, store, market_settings).collect_once(TICK)

    assert run.status == "ok"
    assert run.expected_funds == run.received_funds == len(EQUITY_SAMPLES)
    # bulk endpoints + one NAV per fund + every fund's status (first cycle of the day)
    assert run.requests == 3 + 2 * len(EQUITY_SAMPLES)
    assert {s.ins_code for s in store.states} == EQUITY_SAMPLES
    assert {(s.code, s.title) for s in store.states} == {("A", "مجاز")}
    assert run.tick == TICK.replace(second=0)
    assert {t.ins_code for t in store.ticks} == EQUITY_SAMPLES
    assert all(t.nav_redemption for t in store.ticks)
    assert len(store.market) == 1
    assert store.runs == [run]


async def test_nav_failure_degrades_to_partial(
    http_settings: HttpSettings, market_settings: MarketSettings
) -> None:
    store = MemoryStore()
    with respx.mock as router:
        # Registered first: respx uses the first matching route.
        router.get(f"{BASE}/Fund/GetETFByInsCode/{ATLAS}").mock(return_value=httpx.Response(500))
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            run = await make_collector(client, store, market_settings).collect_once(TICK)

    assert run.status == "partial"
    assert run.received_funds == len(EQUITY_SAMPLES)  # the fund is still written, with a flag
    atlas = next(t for t in store.ticks if t.ins_code == ATLAS)
    assert QualityFlag.NAV_MISSING in QualityFlag(atlas.quality_flags)


async def test_market_watch_failure_fails_the_cycle(
    http_settings: HttpSettings, market_settings: MarketSettings
) -> None:
    store = MemoryStore()
    collector = None
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make_collector(client, store, market_settings)
            await collector.collect_once(TICK)  # first cycle syncs the universe
            router.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(
                side_effect=httpx.ConnectError("down")
            )
            run = await collector.collect_once(TICK.replace(minute=1))

    assert run.status == "failed"
    assert run.received_funds == 0
    assert run.expected_funds == len(EQUITY_SAMPLES)


@pytest.mark.integration
async def test_cycle_and_replay_on_clickhouse(
    ch_client: Any, http_settings: HttpSettings, market_settings: MarketSettings
) -> None:
    await migrate(ch_client)
    repo = Repository(ch_client)
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            run = await make_collector(client, repo, market_settings).collect_once(TICK)
    assert run.status == "ok"

    async def count() -> int:
        r = await ch_client.query("SELECT count() FROM fund_ticks FINAL")
        return int(r.result_rows[0][0])

    assert await count() == len(EQUITY_SAMPLES)
    funds = await repo.load_funds()
    assert {f.ins_code for f in funds if f.fund_type.is_equity} == EQUITY_SAMPLES

    # Replay rebuilds the same ticks from raw_snapshots without duplicating them.
    await ch_client.command("TRUNCATE TABLE fund_ticks")
    validator = Validator(ValidationSettings(), MarketClock(market_settings))
    report = await replay_day(repo, TICK.date(), datetime.now(TEHRAN), validator)
    assert (report.runs, report.ticks) == (1, len(EQUITY_SAMPLES))
    await ch_client.command("OPTIMIZE TABLE fund_ticks FINAL")
    assert await count() == len(EQUITY_SAMPLES)

    row = await ch_client.query(
        "SELECT last_price, nav_redemption, nav_at FROM fund_ticks WHERE ins_code = {i:String}",
        parameters={"i": ATLAS},
    )
    last, nav, nav_at = row.result_rows[0]
    assert (last, nav) == (158000, 157502)
    assert nav_at.hour == 15  # stored in Asia/Tehran


@pytest.mark.integration
async def test_quality_report_on_clickhouse(
    ch_client: Any, http_settings: HttpSettings, market_settings: MarketSettings
) -> None:
    await migrate(ch_client)
    repo = Repository(ch_client)
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make_collector(client, repo, market_settings)
            await collector.collect_once(TICK)
            # Next minute: one fund vanishes from the feed → forward-filled.
            watch = fixture("market_watch.json")
            watch["marketwatch"] = [r for r in watch["marketwatch"] if r["insCode"] != ATLAS]
            router.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(
                return_value=httpx.Response(200, json=watch)
            )
            run = await collector.collect_once(TICK.replace(minute=1))

    assert (run.received_funds, run.filled) == (len(EQUITY_SAMPLES) - 1, 1)
    report = await quality_report(ch_client, TICK.date())
    assert report.ticks == 2 * len(EQUITY_SAMPLES)
    assert report.completeness == pytest.approx(
        (2 * len(EQUITY_SAMPLES) - 1) / (2 * len(EQUITY_SAMPLES))
    )
    assert report.flag_counts["FORWARD_FILLED"] == 1
    assert report.flag_counts["NAV_STALE"] == 2 * len(
        EQUITY_SAMPLES
    )  # recorded NAVs are from the previous day
    checks = {c for c, _, _, _ in report.issues}
    assert {"missing_fund", "nav_stale"} <= checks
    runs = await ch_client.query("SELECT sum(issues), sum(filled) FROM collection_runs")
    assert runs.result_rows[0][1] == 1
