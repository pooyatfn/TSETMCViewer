from __future__ import annotations

from datetime import date

import pytest

from tsetmc_viewer.domain import metrics
from tsetmc_viewer.domain.funds import FundType
from tsetmc_viewer.domain.jalali import format_jalali, jalali_year_start, nowruz, to_jalali


def test_nav_premium() -> None:
    assert metrics.nav_premium(101_000, 100_000, FundType.EQUITY) == pytest.approx(0.01)
    assert metrics.nav_premium(99_000, 100_000, FundType.SECTOR) == pytest.approx(-0.01)
    assert metrics.nav_premium(100_000, None, FundType.EQUITY) is None


def test_leveraged_premium_is_not_computed() -> None:
    # Real sample: اهرم price 67,285 vs published NAV 82,769 → an artificial −18.7%.
    assert metrics.nav_premium(67_285, 82_769, FundType.LEVERAGED) is None


def test_aum_turnover_and_share() -> None:
    net_assets = metrics.aum(157_502, 879_892_240)  # اطلس, recorded
    assert net_assets == 157_502 * 879_892_240
    assert metrics.turnover(1_510_795_429_958, net_assets) == pytest.approx(0.0109, abs=1e-4)
    assert metrics.aum(None, 10) is None
    assert metrics.turnover(1, None) is None


def test_flows_and_buyer_power() -> None:
    assert metrics.net_flow(1_000, 400) == 600
    # avg buy ticket 100 vs avg sell ticket 50 → buyers twice as big
    assert metrics.buyer_power(1_000, 10, 500, 10) == pytest.approx(2.0)
    assert metrics.buyer_power(1_000, 0, 500, 10) is None


def test_robust_center_ignores_missing_and_outliers() -> None:
    assert metrics.robust_center([0.01, -0.34, 0.0, None, 0.02]) == pytest.approx(0.005)
    assert metrics.robust_center([None]) is None


def test_pct_change() -> None:
    assert metrics.pct_change(110, 100) == pytest.approx(0.1)
    assert metrics.pct_change(110, 0) is None


def test_volatility_needs_at_least_five_closes() -> None:
    assert metrics.volatility([100, 101, 99, 102]) is None
    assert metrics.volatility([]) is None


def test_volatility_ignores_zero_prices_and_is_positive() -> None:
    v = metrics.volatility([100, 102, 0, 101, 105, 98, 103])
    assert v is not None
    assert v > 0


def test_volatility_flat_series_is_zero() -> None:
    assert metrics.volatility([100, 100, 100, 100, 100, 100]) == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("gregorian", "jalali"),
    [
        (date(2026, 9, 24), "1405/07/02"),
        (date(2026, 3, 21), "1405/01/01"),
        (date(2026, 3, 20), "1404/12/29"),
        (date(2025, 3, 20), "1403/12/30"),  # 1403 is a leap year
        (date(2024, 3, 20), "1403/01/01"),
        (date(2026, 12, 21), "1405/09/30"),  # Yalda
    ],
)
def test_jalali_conversion(gregorian: date, jalali: str) -> None:
    assert format_jalali(gregorian) == jalali


def test_year_to_date_starts_at_nowruz() -> None:
    assert jalali_year_start(date(2026, 9, 24)) == date(2026, 3, 21)
    assert jalali_year_start(date(2026, 3, 20)) == date(2025, 3, 21)
    assert nowruz(1403) == date(2024, 3, 20)
    assert to_jalali(date(2026, 9, 23)) == (1405, 7, 1)
