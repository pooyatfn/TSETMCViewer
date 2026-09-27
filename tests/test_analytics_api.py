"""End-to-end read side on a real ClickHouse: collect → backfill → API responses."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import fakeredis
import httpx
import pytest
import respx
from fastapi import FastAPI

from support import AGAS, AHROM, ATLAS, BASE, DARA1, EQUITY_SAMPLES, TEHRAN, mock_tsetmc
from tsetmc_viewer.analytics.service import AnalyticsService
from tsetmc_viewer.api.routes import analytics, ops
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.domain.status import FundState
from tsetmc_viewer.pipeline.backfill import BackfillLog, BackfillTick
from tsetmc_viewer.pipeline.history import HistorySync
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.migrate import migrate
from tsetmc_viewer.storage.repository import Repository
from tsetmc_viewer.storage.tickbus import TickBus

pytestmark = pytest.mark.integration
TICK = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)


@pytest.fixture
async def api(ch_client: Any, http_settings: HttpSettings) -> Any:
    await migrate(ch_client)
    repo = Repository(ch_client)
    clock = MarketClock(MarketSettings())
    bus = TickBus(fakeredis.FakeAsyncRedis())
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, repo, clock), repo)
            collector = Collector(
                client, repo, clock, universe, Validator(ValidationSettings(), clock), bus=bus
            )
            await collector.collect_once(TICK)
            funds = await universe.get(TICK.date())
            await HistorySync(client, repo, clock).sync(funds.values(), days=40)

    app = FastAPI()
    app.state.ch, app.state.clock, app.state.bus = ch_client, clock, bus
    app.state.analytics = AnalyticsService(ch_client, clock)
    app.include_router(ops.router)
    app.include_router(analytics.router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_overview(api: httpx.AsyncClient) -> None:
    body = (await api.get("/api/v1/overview")).json()
    assert body["session_date"] == "2026-09-26"
    assert body["session_date_fa"] == "1405/07/04"
    assert body["funds"] == len(EQUITY_SAMPLES)
    assert body["total_aum"] > 0
    assert body["completeness"] == 1.0
    # TSETMC reports points; the API reports a fraction of the previous close
    assert body["index_change"] == pytest.approx(89637.91 / (7257043.42 - 89637.91))


async def test_funds_snapshot_metrics(api: httpx.AsyncClient) -> None:
    funds = {f["ins_code"]: f for f in (await api.get("/api/v1/funds")).json()}
    atlas = funds[ATLAS]
    assert atlas["symbol"] == "اطلس"
    assert atlas["premium"] == pytest.approx(157615 / 157502 - 1)
    assert atlas["aum"] == 157502 * 879892240
    assert funds[AHROM]["premium"] is None  # leveraged
    assert sum(f["share_of_aum"] or 0 for f in funds.values()) == pytest.approx(1.0)
    assert "NAV_STALE" in atlas["quality_flags"]


async def test_fund_detail_and_intraday(api: httpx.AsyncClient) -> None:
    detail = (await api.get(f"/api/v1/funds/{ATLAS}")).json()
    assert detail["snapshot"]["ins_code"] == ATLAS
    assert len(detail["history"]) == 40
    assert detail["returns"]["r_1w"] is not None
    points = (await api.get(f"/api/v1/funds/{ATLAS}/intraday")).json()
    assert [p["last_price"] for p in points] == [158000]
    assert (await api.get("/api/v1/funds/1")).status_code == 404


async def test_fund_history_window_follows_days(api: httpx.AsyncClient) -> None:
    short = (await api.get(f"/api/v1/funds/{ATLAS}?days=14")).json()["history"]
    full = (await api.get(f"/api/v1/funds/{ATLAS}?days=4000")).json()["history"]
    assert 0 < len(short) < len(full) == 40  # the fixture has 40 trading days
    assert short[-1]["trade_date"] == full[-1]["trade_date"]  # same end, shorter window
    assert (await api.get(f"/api/v1/funds/{ATLAS}?days=4001")).status_code == 422


async def test_backfilled_minutes_precede_live_ticks_and_never_replace_them(
    api: httpx.AsyncClient, ch_client: Any
) -> None:
    """ADR 0012: rebuilt minutes show before the first live tick, flagged, without flows/NAV."""
    repo = Repository(ch_client)
    live = await repo.load_live_volumes(TICK.date())
    assert [ts for ts, _ in live[ATLAS]] == [TICK]
    rebuilt = [
        BackfillTick(TICK + timedelta(minutes=m), ATLAS, 157000 + m, 1000 + m, 0, 1, TICK)
        for m in (-2, -1, 0)  # the 10:00 row collides with the live tick and must not show
    ]
    await repo.insert_backfill(rebuilt)
    await repo.insert_backfill_log(
        [BackfillLog(TICK.date(), ATLAS, "stored", 1, 1, 2, "", TICK)]
    )  # fmt: skip
    assert await repo.backfilled_funds(TICK.date()) == {ATLAS}

    points = (await api.get(f"/api/v1/funds/{ATLAS}/intraday")).json()
    assert [p["backfilled"] for p in points] == [True, True, False]
    assert [p["last_price"] for p in points] == [156998, 156999, 158000]
    assert points[0]["nav"] is None
    assert points[0]["ind_net_flow"] is None


async def test_sessions_lists_days_with_data_and_flags_intraday_depth(
    api: httpx.AsyncClient,
) -> None:
    """Backs the panel's session picker (docs/10-limitations.md #2): newest first."""
    sessions = (await api.get("/api/v1/sessions")).json()
    today = next(s for s in sessions if s["day"] == "2026-09-26")
    assert today["day_fa"] == "1405/07/04"
    assert today["has_intraday"] is False  # the fixture collected a single tick that day
    assert [s["day"] for s in sessions] == sorted((s["day"] for s in sessions), reverse=True)

    # `?date=` picks any listed session, not just the latest.
    picked = (await api.get("/api/v1/overview?date=2026-09-26")).json()
    assert picked["session_date"] == "2026-09-26"
    assert picked["is_live"] is False  # a picked-but-past session is never "live"


async def test_fund_status_is_shown_and_counted(api: httpx.AsyncClient, ch_client: Any) -> None:
    funds = {f["ins_code"]: f for f in (await api.get("/api/v1/funds")).json()}
    assert funds[ATLAS]["status_kind"] == "open"  # fetched by the first cycle of the day
    assert funds[ATLAS]["status_title"] == "مجاز"
    assert (await api.get("/api/v1/overview")).json()["not_trading"] == 0

    later = TICK + timedelta(minutes=3)
    await Repository(ch_client).insert_fund_states(
        [FundState(later, AGAS, "AS", "مجاز-متوقف", 1, later)]
    )  # fmt: skip
    # In production the status rows land with a tick; here, bump it like the collector would.
    await api._transport.app.state.bus.bump("status")  # type: ignore[attr-defined]
    funds = {f["ins_code"]: f for f in (await api.get("/api/v1/funds")).json()}
    agas = funds[AGAS]
    assert (agas["status_kind"], agas["status_title"], agas["under_supervision"]) == (
        "suspended", "مجاز-متوقف", True,
    )  # fmt: skip
    assert (await api.get("/api/v1/overview")).json()["not_trading"] == 1


async def test_flows_returns_and_market(api: httpx.AsyncClient) -> None:
    flows = (await api.get("/api/v1/flows/daily?days=30")).json()
    official = [f for f in flows if not f["estimated"]]
    live = [f for f in flows if f["estimated"]]
    assert official  # official history
    assert live  # plus today's live estimate
    assert {f["trade_date"] for f in live} == {"2026-09-26"}
    returns = {r["ins_code"]: r for r in (await api.get("/api/v1/returns")).json()}
    assert set(returns) == {ATLAS, AHROM, DARA1}
    market = (await api.get("/api/v1/market/flow")).json()
    assert len(market) == 1
    assert market[0]["index_value"] == pytest.approx(7257043.42)


async def test_risk_return_covers_every_equity_fund(api: httpx.AsyncClient) -> None:
    """docs/10-limitations.md #2: one volatility/return point per equity fund, AUM sized."""
    risk = {r["ins_code"]: r for r in (await api.get("/api/v1/risk")).json()}
    assert set(risk) == EQUITY_SAMPLES  # every equity fund, even ones without daily history yet
    for row in risk.values():
        assert row["fund_type"]
        # The fixture history is short, so volatility may legitimately be null (< 5 closes);
        # when present it must be a real, non-negative annualised number.
        if row["volatility"] is not None:
            assert row["volatility"] >= 0


async def test_responses_are_cached_per_tick(api: httpx.AsyncClient) -> None:
    first = await api.get("/api/v1/funds")
    second = await api.get("/api/v1/funds")
    assert first.headers["x-tick"] == TICK.isoformat()
    assert (first.headers["x-cache"], second.headers["x-cache"]) == ("miss", "hit")
    etag = second.headers["etag"]
    assert (await api.get("/api/v1/funds", headers={"If-None-Match": etag})).status_code == 304


async def test_quality_endpoint(api: httpx.AsyncClient) -> None:
    body = (await api.get("/api/v1/quality")).json()
    assert body["ticks"] == len(EQUITY_SAMPLES)
    assert body["completeness"] == 1.0


async def test_market_premium_median_and_weighted(api: httpx.AsyncClient) -> None:
    overview = (await api.get("/api/v1/overview")).json()
    funds = (await api.get("/api/v1/funds")).json()
    premiums = [(f["premium"], f["aum"]) for f in funds if f["premium"] is not None]
    expected = sum(p * a for p, a in premiums) / sum(a for _, a in premiums)
    assert overview["weighted_premium"] == pytest.approx(expected)
    assert overview["holiday_today"] is None  # 2026-09-26 is an ordinary Saturday

    intraday = (await api.get("/api/v1/premium/intraday")).json()
    daily = (await api.get("/api/v1/premium/daily")).json()
    assert len(intraday) == 1
    assert intraday[0]["funds"] == len(premiums)  # leveraged funds (no comparable NAV) excluded
    assert intraday[0]["weighted"] == pytest.approx(expected)
    # The end-of-day rollup gives the same numbers for the session.
    assert [d["at"] for d in daily] == ["2026-09-26"]
    assert daily[0]["median"] == pytest.approx(overview["median_premium"])
    assert daily[0]["weighted"] == pytest.approx(expected)


async def test_calendar_lists_holidays_and_observed_closures(
    api: httpx.AsyncClient, ch_client: Any
) -> None:
    await Repository(ch_client).record_market_day(
        date(2026, 10, 5),
        trading=False,
        note="بسته",
        at=datetime(2026, 10, 5, 9, 30, tzinfo=TEHRAN),
    )
    days = {d["day"]: d for d in (await api.get("/api/v1/calendar?year=1405")).json()}
    assert days["2026-08-04"]["reason"] == "اربعین"
    assert days["2026-08-04"]["source"] == "official"
    assert days["2026-10-05"] == {
        "day": "2026-10-05", "day_fa": "1405/07/13", "trading": False, "reason": "بسته",
        "source": "observed",
    }  # fmt: skip
    assert all(d["source"] != "weekend" for d in days.values())
