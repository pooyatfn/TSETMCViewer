from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from support import AGAS, AHROM, ATLAS, DARA1, TEHRAN, YAGHUT, fixture
from tsetmc_viewer.domain.funds import FundRef, FundType
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.pipeline.cycle import parse_responses, process_cycle
from tsetmc_viewer.pipeline.transform import build_fund_ticks
from tsetmc_viewer.sources.http import RawResponse
from tsetmc_viewer.sources.tsetmc_models import (
    parse_client_types,
    parse_etf,
    parse_market_watch,
)

TS = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)


def ref(ins: str, isin: str, fund_type: FundType = FundType.EQUITY) -> FundRef:
    return FundRef(ins, "", "", isin, fund_type)


UNIVERSE = {
    ATLAS: ref(ATLAS, "IRT3SATF0001"),
    AGAS: ref(AGAS, "IRT3SAGF0001"),
    AHROM: ref(AHROM, "IRT1AHRM0001", FundType.LEVERAGED),
    DARA1: ref(DARA1, "IRT1DARA0001"),
}


def navs() -> dict[str, object]:
    return {ins: parse_etf(fixture(f"etf_{ins}.json")) for ins in UNIVERSE}


def build(**overrides: object):  # type: ignore[no-untyped-def]
    kwargs: dict[str, object] = {
        "ts": TS,
        "run_id": uuid4(),
        "ingested_at": TS,
        "universe": UNIVERSE,
        "market_watch": parse_market_watch(fixture("market_watch.json")),
        "client_types": parse_client_types(fixture("client_type_all.json")),
        "navs": navs(),
    }
    kwargs.update(overrides)
    return build_fund_ticks(**kwargs)  # type: ignore[arg-type]


def test_one_tick_per_fund_in_universe() -> None:
    batch = build()
    assert {t.ins_code for t in batch.ticks} == set(UNIVERSE)
    assert batch.missing == []
    assert all(t.ts == TS for t in batch.ticks)


def test_atlas_tick_values() -> None:
    tick = next(t for t in build().ticks if t.ins_code == ATLAS)
    assert (tick.last_price, tick.close_price, tick.volume) == (158000, 157615, 9585358)
    assert (tick.nav_redemption, tick.nav_subscription) == (157502, 159005)
    assert tick.nav_at == datetime(2026, 9, 23, 15, 58, 4, tzinfo=TEHRAN)
    assert (tick.bid_price, tick.ask_price) == (157974, 158000)
    assert QualityFlag(tick.quality_flags) == QualityFlag.FLOW_VALUE_ESTIMATED


def test_flow_values_are_volume_times_vwap() -> None:
    tick = next(t for t in build().ticks if t.ins_code == AHROM)
    vwap = tick.value / tick.volume
    assert tick.ind_buy_value == pytest.approx(tick.ind_buy_volume * vwap, abs=1)
    assert tick.ind_buy_volume + tick.inst_buy_volume > 0


def test_missing_nav_and_client_type_are_flagged_not_dropped() -> None:
    batch = build(navs={}, client_types=[])
    assert len(batch.ticks) == len(UNIVERSE)
    for t in batch.ticks:
        flags = QualityFlag(t.quality_flags)
        assert QualityFlag.NAV_MISSING in flags
        assert QualityFlag.CLIENT_TYPE_MISSING in flags
        assert t.nav_redemption is None


def test_fund_absent_from_market_watch_is_reported_missing() -> None:
    ghost = "999"
    batch = build(universe={**UNIVERSE, ghost: ref(ghost, "IRT1GHST0001")})
    assert batch.missing == [ghost]


def test_secondary_board_turnover_rolls_up_into_primary() -> None:
    rows = parse_market_watch(fixture("market_watch.json"))
    atlas = next(r for r in rows if r.ins_code == ATLAS)
    block = atlas.model_copy(
        update={"ins_code": "block1", "isin": "IRT3SATF0002", "volume": 1000, "value": 157_000_000}
    )
    tick = next(t for t in build(market_watch=[*rows, block]).ticks if t.ins_code == ATLAS)
    assert (tick.block_volume, tick.block_value) == (1000, 157_000_000)


def test_fixed_income_is_not_in_equity_universe() -> None:
    assert YAGHUT not in {t.ins_code for t in build().ticks}


def _raw(endpoint: str, body: bytes, status: int = 200, ins: str = "") -> RawResponse:
    return RawResponse("tsetmc", endpoint, "", status, body, TS, 1, ins_code=ins)


def test_parse_responses_collects_errors_without_raising() -> None:
    parsed = parse_responses(
        [
            _raw("market_watch", b"not json"),
            _raw("client_type_all", b"{}", status=503),
            _raw("etf", b'{"etf": null}', ins="1"),
        ]
    )
    assert parsed.market_watch is None
    assert parsed.navs == {}
    assert len(parsed.errors) == 2


def test_process_cycle_without_market_watch_marks_everything_missing() -> None:
    result = process_cycle(responses=[], universe=UNIVERSE, ts=TS, run_id=uuid4(), ingested_at=TS)
    assert result.batch.ticks == []
    assert set(result.batch.missing) == set(UNIVERSE)
