from __future__ import annotations

from datetime import datetime

import pytest

from support import ATLAS, TEHRAN, YAGHUT, fixture
from tsetmc_viewer.sources.tsetmc_models import (
    MarketWatchRow,
    PayloadError,
    parse_client_types,
    parse_etf,
    parse_instrument_info,
    parse_market_overview,
    parse_market_watch,
    tehran_datetime,
)


def test_market_watch_field_mapping_matches_closing_price_info() -> None:
    rows = {r.ins_code: r for r in parse_market_watch(fixture("market_watch.json"))}
    atlas = rows[ATLAS]
    # Values cross-checked against GetClosingPriceInfo for the same instrument.
    assert atlas.symbol == "اطلس"
    assert atlas.isin == "IRT3SATF0001"
    assert atlas.sector == "68"
    assert (atlas.last_price, atlas.close_price) == (158000, 157615)
    assert (atlas.open_price, atlas.low_price, atlas.high_price) == (155951, 154463, 159006)
    assert atlas.prev_close == 154380
    assert (atlas.volume, atlas.value, atlas.trade_count) == (9585358, 1510795429958, 4441)
    assert atlas.top is not None
    assert (atlas.top.bid_price, atlas.top.ask_price) == (157974, 158000)
    assert len(atlas.best_limits) == 5


def test_symbols_are_normalized() -> None:
    rows = parse_market_watch(fixture("market_watch.json"))
    assert "دارا یکم" in {r.symbol for r in rows}  # recorded as "دارا يكم"


def test_client_types() -> None:
    rows = {r.ins_code: r for r in parse_client_types(fixture("client_type_all.json"))}
    assert rows
    assert all(r.ind_buy_volume >= 0 for r in rows.values())


def test_etf_nav_and_timestamp() -> None:
    nav = parse_etf(fixture(f"etf_{ATLAS}.json"))
    assert nav is not None
    assert (nav.redemption, nav.subscription) == (157502, 159005)
    assert nav.nav_at == datetime(2026, 9, 23, 15, 58, 4, tzinfo=TEHRAN)


def test_instrument_info_fund_fields() -> None:
    info = parse_instrument_info(fixture(f"instrument_info_{YAGHUT}.json"))
    assert info.isin == "IRT1YGHT0001"
    assert "درآمد ثابت" in info.fund_desc
    assert info.units == 13536478511
    assert info.market == "بازار بورس"


def test_market_overview() -> None:
    o = parse_market_overview(fixture("market_overview.json"))
    assert o.index_value == pytest.approx(7257043.42)
    assert o.state == "F"


@pytest.mark.parametrize(
    ("deven", "heven", "expected"),
    [
        (20260923, 155804, datetime(2026, 9, 23, 15, 58, 4, tzinfo=TEHRAN)),
        (20260926, 91530, datetime(2026, 9, 26, 9, 15, 30, tzinfo=TEHRAN)),  # lost leading 0
        (0, 0, None),
        (20261399, 0, None),  # invalid date
    ],
)
def test_tehran_datetime(deven: int, heven: int, expected: datetime | None) -> None:
    assert tehran_datetime(deven, heven) == expected


def test_float_and_null_quantities_become_ints() -> None:
    row = MarketWatchRow.model_validate(
        {
            "insCode": 1,
            "lva": "x",
            "lvc": "y",
            "insID": "IRT1XXXX0001",
            "csv": "68 ",
            "pdv": 1000.0,
            "pcl": None,
            "pf": 0,
            "pmn": 0,
            "pmx": 0,
            "py": 990.0,
            "qtj": 5.0,
            "qtc": 5000.0,
            "ztt": 1.0,
            "pMax": 0,
            "pMin": 0,
            "hEven": 90000,
        }
    )
    assert (row.ins_code, row.last_price, row.close_price, row.volume) == ("1", 1000, 0, 5)


def test_wrong_envelope_raises() -> None:
    with pytest.raises(PayloadError):
        parse_market_watch({"unexpected": []})
