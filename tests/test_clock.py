from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import MarketSettings

TEHRAN = ZoneInfo("Asia/Tehran")
# 2026-09-26 is a Saturday (first trading day of the Iranian week).
SAT = datetime(2026, 9, 26, tzinfo=TEHRAN)


@pytest.fixture
def clock(market_settings: MarketSettings) -> MarketClock:
    return MarketClock(market_settings)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (SAT.replace(hour=8, minute=59), False),
        (SAT.replace(hour=9), True),
        (SAT.replace(hour=12, minute=30), True),
        (SAT.replace(hour=12, minute=31), False),
        (datetime(2026, 9, 24, 10, tzinfo=TEHRAN), False),  # Thursday
        (datetime(2026, 9, 25, 10, tzinfo=TEHRAN), False),  # Friday
        (datetime(2026, 9, 30, 10, tzinfo=TEHRAN), True),  # Wednesday
    ],
)
def test_is_open(clock: MarketClock, moment: datetime, expected: bool) -> None:
    assert clock.is_open(moment) is expected


def test_is_open_converts_from_utc(clock: MarketClock) -> None:
    # 06:00 UTC == 09:30 Tehran (UTC+3:30, no DST since 2022).
    assert clock.is_open(datetime(2026, 9, 26, 6, 0, tzinfo=ZoneInfo("UTC")))


def test_next_open_skips_weekend(clock: MarketClock) -> None:
    thursday_noon = datetime(2026, 9, 24, 13, tzinfo=TEHRAN)
    assert clock.next_open(thursday_noon) == SAT.replace(hour=9)


def test_next_open_same_day_before_open(clock: MarketClock) -> None:
    assert clock.next_open(SAT.replace(hour=7)) == SAT.replace(hour=9)


def test_seconds_until_next_tick_aligns_to_minute(clock: MarketClock) -> None:
    moment = SAT.replace(hour=10, minute=0, second=45)
    assert clock.seconds_until_next_tick(moment, 60) == pytest.approx(15)


def test_floor_minute() -> None:
    moment = SAT.replace(hour=10, minute=5, second=59, microsecond=999)
    assert MarketClock.floor_minute(moment) == SAT.replace(hour=10, minute=5)
