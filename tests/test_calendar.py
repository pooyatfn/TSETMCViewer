"""Trading calendar: official holidays, extra closures, runtime observations, session guard."""

from __future__ import annotations

import logging
from datetime import date, datetime

import pytest
import respx

from support import BASE, TEHRAN, MemoryStore, mock_tsetmc
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.domain.calendar import HolidayCalendar
from tsetmc_viewer.domain.jalali import from_jalali
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient

WEEKDAYS = MarketSettings().trading_weekdays
ARBAEEN = date(2026, 8, 4)  # 13 Mordad 1405, a Tuesday


def test_1405_official_holidays() -> None:
    days = HolidayCalendar(WEEKDAYS).official(1405)
    assert days[from_jalali(1405, 1, 13)] == "روز طبیعت"
    assert days[from_jalali(1405, 11, 22)] == "پیروزی انقلاب اسلامی"
    assert days[ARBAEEN] == "اربعین"
    # Two occasions on one day are merged, not double-counted.
    assert days[from_jalali(1405, 3, 14)] == "رحلت امام خمینی و عید غدیر"
    assert days[from_jalali(1405, 1, 1)] == "نوروز و عید فطر"
    assert len(days) == 26


def test_precedence_observed_over_extra_over_official() -> None:
    cal = HolidayCalendar(WEEKDAYS, extra={date(2026, 10, 5): "اعلام بورس"})
    assert cal.status(ARBAEEN).source == "official"
    assert not cal.is_trading_day(ARBAEEN)
    assert cal.holiday_name(date(2026, 10, 5)) == "اعلام بورس"
    assert cal.status(date(2026, 9, 24)).source == "weekend"  # Thursday
    assert cal.holiday_name(date(2026, 9, 24)) is None  # weekends are not "holidays"
    cal.observe(ARBAEEN, trading=True, note="list was wrong")
    assert cal.is_trading_day(ARBAEEN)
    cal.observe(date(2026, 9, 26), trading=False, note="closed")
    assert cal.holiday_name(date(2026, 9, 26)) == "closed"


def test_year_without_lunar_table_uses_solar_rules_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cal = HolidayCalendar(WEEKDAYS)
    with caplog.at_level(logging.WARNING):
        assert not cal.is_trading_day(from_jalali(1406, 1, 12))  # solar rule still applies
        cal.is_trading_day(from_jalali(1406, 2, 1))
    assert sum("no lunar holiday table" in r.getMessage() for r in caplog.records) == 1


def test_clock_skips_holidays_unless_disabled() -> None:
    clock = MarketClock(MarketSettings())
    monday_after_close = datetime(2026, 8, 3, 13, 0, tzinfo=TEHRAN)
    assert not clock.is_open(datetime(2026, 8, 4, 10, 0, tzinfo=TEHRAN))
    assert clock.next_open(monday_after_close).date() == date(2026, 8, 5)
    assert clock.holiday(datetime(2026, 8, 4, 10, 0, tzinfo=TEHRAN)) == "اربعین"
    plain = MarketClock(MarketSettings(holidays=False))
    assert plain.is_open(datetime(2026, 8, 4, 10, 0, tzinfo=TEHRAN))


# --- session guard -------------------------------------------------------------------------
# The recorded market overview reports marketActivityDEven = 2026-09-23 (a Wednesday).


class FixedClock(MarketClock):
    def __init__(self, now: datetime, **market: object) -> None:
        super().__init__(MarketSettings(**market))  # type: ignore[arg-type]
        self._now = now

    def now(self) -> datetime:
        return self._now


def make(client: TsetmcClient, store: MemoryStore, clock: MarketClock) -> Collector:
    universe = FundUniverse(UniverseSync(client, store, clock), store)
    return Collector(client, store, clock, universe, Validator(ValidationSettings(), clock))


async def test_guard_confirms_a_trading_day(http_settings: HttpSettings) -> None:
    now = datetime(2026, 9, 23, 9, 5, tzinfo=TEHRAN)
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            assert await make(client, store, FixedClock(now))._session_confirmed(now)
    assert not store.market_days


async def test_guard_waits_then_records_an_unannounced_closure(
    http_settings: HttpSettings,
) -> None:
    early = datetime(2026, 9, 26, 9, 5, tzinfo=TEHRAN)  # Saturday; TSETMC still shows Wednesday
    late = datetime(2026, 9, 26, 9, 25, tzinfo=TEHRAN)
    store = MemoryStore()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            clock = FixedClock(early)
            collector = make(client, store, clock)
            assert not await collector._session_confirmed(early)  # maybe no trade yet
            assert not store.market_days
            assert not await collector._session_confirmed(late)  # past the guard
    assert store.market_days[date(2026, 9, 26)][0] is False
    assert not clock.is_open(late)  # the loop now sleeps until the next session


async def test_listed_holiday_that_trades_is_corrected(http_settings: HttpSettings) -> None:
    now = datetime(2026, 9, 23, 9, 30, tzinfo=TEHRAN)
    clock = FixedClock(now, extra_holidays={date(2026, 9, 23): "اشتباه"})
    store = MemoryStore()
    assert not clock.is_open(now)
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            await make(client, store, clock)._check_listed_holiday(now)
    assert clock.is_open(now)
    assert store.market_days[date(2026, 9, 23)][0] is True
