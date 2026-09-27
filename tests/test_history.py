from __future__ import annotations

from datetime import date, datetime

import respx

from support import AGAS, AHROM, ATLAS, BASE, DARA1, TEHRAN, MemoryStore, fixture, mock_tsetmc
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import HttpSettings, MarketSettings
from tsetmc_viewer.domain.funds import FundRef, FundType
from tsetmc_viewer.pipeline.history import HistorySync, merge_history
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import parse_client_type_history, parse_daily_prices

NOW = datetime(2026, 9, 24, 16, 0, tzinfo=TEHRAN)


def test_merge_joins_prices_and_official_flows_by_date() -> None:
    prices = parse_daily_prices(fixture(f"daily_history_{ATLAS}.json"))
    flows = parse_client_type_history(fixture(f"client_history_{ATLAS}.json"))
    rows = merge_history(ATLAS, prices, flows, days=10, updated_at=NOW)
    assert len(rows) == 10
    latest = rows[0]
    assert latest.trade_date == date(2026, 9, 23)
    assert (latest.close_price, latest.volume) == (157615, 9585358)
    # Official values (not estimates) and the volume identity holds.
    assert latest.ind_buy_value == 1224665895331
    assert latest.ind_buy_volume + latest.inst_buy_volume == latest.volume
    assert [r.trade_date for r in rows] == sorted((r.trade_date for r in rows), reverse=True)


def test_merge_keeps_price_days_without_flows() -> None:
    prices = parse_daily_prices(fixture(f"daily_history_{ATLAS}.json"))
    rows = merge_history(ATLAS, prices, [], days=3, updated_at=NOW)
    assert len(rows) == 3
    assert all(r.ind_buy_value == 0 for r in rows)


async def test_sync_reports_failures_and_writes_the_rest(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    funds = [
        FundRef(ATLAS, "اطلس", "", "IRT3SATF0001", FundType.EQUITY),
        FundRef(AHROM, "اهرم", "", "IRT1AHRM0001", FundType.LEVERAGED),
        FundRef(DARA1, "دارا یکم", "", "IRT1DARA0001", FundType.EQUITY),
        FundRef(AGAS, "آگاس", "", "IRT3SAGF0001", FundType.EQUITY),  # no recorded history → 404
    ]
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            report = await HistorySync(client, store, MarketClock(MarketSettings())).sync(
                funds, days=30
            )
    assert report.failed == ["آگاس"]
    assert report.rows == 3 * 30
    assert {r.ins_code for r in store.history} == {ATLAS, AHROM, DARA1}
