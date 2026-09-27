from __future__ import annotations

from datetime import date, datetime

import httpx
import pytest
import respx

from support import (
    AGAS,
    AHROM,
    AKAM,
    ATLAS,
    BASE,
    CHATR,
    DARA1,
    EQUITY_SAMPLES,
    GARANTI,
    YAGHUT,
    MemoryStore,
    mock_tsetmc,
)
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import HttpSettings, MarketSettings
from tsetmc_viewer.domain.funds import FundRef, FundType
from tsetmc_viewer.pipeline.universe import FundRecord, FundUniverse, UniverseError, UniverseSync
from tsetmc_viewer.sources.tsetmc import TsetmcClient


@pytest.fixture
def clock(market_settings: MarketSettings) -> MarketClock:
    return MarketClock(market_settings)


async def test_sync_classifies_recorded_funds(
    http_settings: HttpSettings, clock: MarketClock
) -> None:
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            refs = {r.ins_code: r for r in await UniverseSync(client, store, clock).sync()}

    assert refs[ATLAS].fund_type is FundType.EQUITY
    assert refs[AHROM].fund_type is FundType.LEVERAGED
    assert refs[YAGHUT].fund_type is FundType.FIXED_INCOME
    assert refs[ATLAS].units == 879892240
    # Only primary boards (…0001) of fund units; secondary boards and options excluded.
    assert all(r.isin.startswith("IRT") and r.isin.endswith("0001") for r in refs.values())
    assert refs[CHATR].fund_type is FundType.SECTOR
    assert refs[AKAM].fund_type is FundType.FIXED_INCOME
    assert refs[GARANTI].fund_type is FundType.MIXED
    # Raw instrument-info responses are persisted too.
    assert {r.endpoint for r in store.raw} == {"market_watch", "instrument_info"}
    assert store.units[(clock.now().date(), ATLAS)] == 879892240


async def test_sync_deactivates_vanished_funds(
    http_settings: HttpSettings, clock: MarketClock
) -> None:
    store = MemoryStore()
    old = FundRef("gone", "قدیمی", "", "IRT1OLDX0001", FundType.EQUITY)
    await store.upsert_funds([FundRecord(old, "", "")], datetime(2026, 1, 1))
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            await UniverseSync(client, store, clock).sync()
    assert store.funds["gone"][0].is_active is False


async def test_universe_is_equity_only_and_cached(
    http_settings: HttpSettings, clock: MarketClock
) -> None:
    store = MemoryStore()
    today = clock.now().date()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, store, clock), store)
            funds = await universe.get(today)
            calls = router.calls.call_count
            again = await universe.get(today)
            assert router.calls.call_count == calls  # served from memory
    assert set(funds) == EQUITY_SAMPLES == {ATLAS, AGAS, AHROM, DARA1, CHATR}
    assert again is funds


async def test_universe_falls_back_to_last_known_list(
    http_settings: HttpSettings, clock: MarketClock
) -> None:
    store = MemoryStore()
    known = FundRef(ATLAS, "اطلس", "", "IRT3SATF0001", FundType.EQUITY)
    await store.upsert_funds([FundRecord(known, "", "")], datetime(2026, 9, 20))
    with respx.mock as router:
        router.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(return_value=httpx.Response(503))
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, store, clock), store)
            funds = await universe.get(date(2026, 9, 26))
    assert set(funds) == {ATLAS}


async def test_universe_without_any_data_raises(
    http_settings: HttpSettings, clock: MarketClock
) -> None:
    store = MemoryStore()
    with respx.mock as router:
        router.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(return_value=httpx.Response(503))
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, store, clock), store)
            with pytest.raises(UniverseError):
                await universe.get(date(2026, 9, 26))
