"""Every validation check and repair, one scenario each."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from support import TEHRAN
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import MarketSettings, ValidationSettings
from tsetmc_viewer.domain.quality import Check, QualityFlag, Severity
from tsetmc_viewer.pipeline.transform import FundTick, TickBatch
from tsetmc_viewer.pipeline.validate import ValidationResult, Validator

T0 = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)  # Saturday, market open
FUND = "fund-1"
BAND = (95_000, 105_000)


def make_tick(ts: datetime = T0, **overrides: Any) -> FundTick:
    base: dict[str, Any] = {
        "ts": ts,
        "ins_code": FUND,
        "run_id": uuid4(),
        "last_price": 100_000,
        "close_price": 100_000,
        "open_price": 99_000,
        "high_price": 101_000,
        "low_price": 98_000,
        "prev_close": 100_000,
        "volume": 1_000,
        "value": 100_000_000,
        "trade_count": 10,
        "block_volume": 0,
        "block_value": 0,
        "nav_redemption": 100_500,
        "nav_subscription": 101_000,
        "nav_at": ts - timedelta(minutes=2),
        "bid_price": 99_900,
        "bid_volume": 5,
        "ask_price": 100_000,
        "ask_volume": 5,
        "ind_buy_volume": 800,
        "ind_sell_volume": 700,
        "inst_buy_volume": 200,
        "inst_sell_volume": 300,
        "ind_buy_value": 0,
        "ind_sell_value": 0,
        "inst_buy_value": 0,
        "inst_sell_value": 0,
        "ind_buy_count": 5,
        "ind_sell_count": 5,
        "inst_buy_count": 1,
        "inst_sell_count": 1,
        "quality_flags": int(QualityFlag.FLOW_VALUE_ESTIMATED),
        "ingested_at": ts,
    }
    return FundTick(**(base | overrides))


@pytest.fixture
def validator() -> Validator:
    return Validator(ValidationSettings(), MarketClock(MarketSettings()))


def run(
    v: Validator,
    ticks: list[FundTick],
    *,
    ts: datetime = T0,
    missing: list[str] | None = None,
    feed_heven: int = 100000,
) -> ValidationResult:
    batch = TickBatch(ticks=ticks, missing=missing or [], bands={FUND: BAND}, feed_heven=feed_heven)
    return v.validate(batch, ts=ts, run_id=uuid4(), ingested_at=ts)


def flags(tick: FundTick) -> QualityFlag:
    return QualityFlag(tick.quality_flags)


def checks(result: ValidationResult) -> list[Check]:
    return [i.check for i in result.issues]


def test_clean_tick_passes_untouched(validator: Validator) -> None:
    tick = make_tick()
    result = run(validator, [tick])
    assert result.ticks == [tick]
    assert result.issues == []
    assert (result.filled, result.repaired) == (0, 0)


# --- price band -------------------------------------------------------------------


def test_price_outside_band_is_replaced_with_previous(validator: Validator) -> None:
    run(validator, [make_tick()])
    bad = make_tick(T0 + timedelta(minutes=1), last_price=150_000, high_price=150_000)
    result = run(validator, [bad], ts=bad.ts, feed_heven=100100)
    tick = result.ticks[0]
    assert tick.last_price == 100_000
    assert QualityFlag.PRICE_OUT_OF_RANGE in flags(tick)
    issue = result.issues[0]
    assert (issue.check, issue.severity, issue.action) == (
        Check.PRICE_OUT_OF_BAND,
        Severity.ERROR,
        "replaced_with_previous",
    )


def test_price_outside_band_without_history_is_kept_and_flagged(validator: Validator) -> None:
    result = run(validator, [make_tick(last_price=150_000, high_price=150_000)])
    assert result.ticks[0].last_price == 150_000
    assert QualityFlag.PRICE_OUT_OF_RANGE in flags(result.ticks[0])
    assert result.issues[0].action == "kept"


def test_no_band_check_before_first_trade(validator: Validator) -> None:
    result = run(validator, [make_tick(trade_count=0, last_price=0, close_price=0)])
    assert Check.PRICE_OUT_OF_BAND not in checks(result)


# --- OHLC ------------------------------------------------------------------------------


def test_high_low_are_recomputed_to_contain_last(validator: Validator) -> None:
    result = run(validator, [make_tick(last_price=102_000, high_price=101_000)])
    tick = result.ticks[0]
    assert (tick.high_price, tick.low_price) == (102_000, 98_000)
    assert QualityFlag.RANGE_REPAIRED in flags(tick)
    assert checks(result) == [Check.OHLC_INCONSISTENT]


# --- cumulative counters -------------------------------------------------------------


def test_cumulative_decrease_keeps_previous_values(validator: Validator) -> None:
    run(validator, [make_tick(volume=5_000, value=500_000_000, ind_buy_volume=4_000)])
    later = T0 + timedelta(minutes=1)
    result = run(validator, [make_tick(later)], ts=later, feed_heven=100100)
    tick = result.ticks[0]
    assert (tick.volume, tick.value, tick.ind_buy_volume) == (5_000, 500_000_000, 4_000)
    assert QualityFlag.CUMULATIVE_DECREASE in flags(tick)
    assert "volume 5000→1000" in result.issues[0].detail


def test_counters_reset_on_a_new_day(validator: Validator) -> None:
    run(validator, [make_tick(volume=5_000)])
    next_day = T0 + timedelta(days=1)  # Sunday
    result = run(validator, [make_tick(next_day)], ts=next_day)
    assert Check.CUMULATIVE_DECREASE not in checks(result)


# --- individual / institutional ----------------------------------------------------------


def test_client_volume_mismatch_is_edge_triggered(validator: Validator) -> None:
    first = run(validator, [make_tick(ind_buy_volume=100)])
    assert QualityFlag.CLIENT_VOLUME_MISMATCH in flags(first.ticks[0])
    assert checks(first) == [Check.CLIENT_VOLUME_MISMATCH]

    t1 = T0 + timedelta(minutes=1)
    second = run(validator, [make_tick(t1, ind_buy_volume=100)], ts=t1, feed_heven=100100)
    assert QualityFlag.CLIENT_VOLUME_MISMATCH in flags(second.ticks[0])
    assert second.issues == []  # still flagged, not logged again

    t2 = T0 + timedelta(minutes=2)
    run(validator, [make_tick(t2)], ts=t2, feed_heven=100200)  # resolved
    t3 = T0 + timedelta(minutes=3)
    mismatch = make_tick(t3, volume=5_000, value=500_000_000)  # buys still sum to 1_000
    third = run(validator, [mismatch], ts=t3, feed_heven=100300)
    assert checks(third) == [Check.CLIENT_VOLUME_MISMATCH]  # new episode, logged again


# --- NAV -----------------------------------------------------------------------------------


def test_missing_nav_is_carried_forward(validator: Validator) -> None:
    run(validator, [make_tick()])
    t1 = T0 + timedelta(minutes=1)
    no_nav = make_tick(
        t1,
        nav_redemption=None,
        nav_subscription=None,
        nav_at=None,
        quality_flags=int(QualityFlag.FLOW_VALUE_ESTIMATED | QualityFlag.NAV_MISSING),
    )
    result = run(validator, [no_nav], ts=t1, feed_heven=100100)
    tick = result.ticks[0]
    assert tick.nav_redemption == 100_500
    assert tick.nav_at == T0 - timedelta(minutes=2)
    assert {QualityFlag.NAV_MISSING, QualityFlag.NAV_CARRIED} <= set(flags(tick))
    assert result.issues[0].action == "carried_forward"


def test_stale_nav_is_flagged(validator: Validator) -> None:
    result = run(validator, [make_tick(nav_at=T0 - timedelta(hours=18))])
    assert QualityFlag.NAV_STALE in flags(result.ticks[0])
    assert result.issues[0].severity is Severity.INFO


def test_nav_jump_is_flagged_not_changed(validator: Validator) -> None:
    run(validator, [make_tick()])
    t1 = T0 + timedelta(minutes=1)
    result = run(validator, [make_tick(t1, nav_redemption=130_000)], ts=t1, feed_heven=100100)
    assert result.ticks[0].nav_redemption == 130_000
    assert QualityFlag.NAV_JUMP in flags(result.ticks[0])
    assert checks(result) == [Check.NAV_JUMP]


# --- completeness ---------------------------------------------------------------------------


def test_missing_fund_is_forward_filled(validator: Validator) -> None:
    run(validator, [make_tick()])
    t1 = T0 + timedelta(minutes=1)
    result = run(validator, [], ts=t1, missing=[FUND])
    assert len(result.ticks) == 1
    tick = result.ticks[0]
    assert tick.ts == t1
    assert tick.last_price == 100_000
    assert QualityFlag.FORWARD_FILLED in flags(tick)
    assert result.filled == 1
    assert result.issues[0].action == "forward_filled"


def test_missing_fund_without_history_is_dropped(validator: Validator) -> None:
    result = run(validator, [], missing=[FUND])
    assert result.ticks == []
    assert result.issues[0].action == "dropped"


def test_gap_between_ticks_is_filled_minute_by_minute(validator: Validator) -> None:
    run(validator, [make_tick()])
    t4 = T0 + timedelta(minutes=4)
    result = run(validator, [make_tick(t4)], ts=t4, feed_heven=100400)
    assert [t.ts for t in result.ticks] == [T0 + timedelta(minutes=m) for m in (1, 2, 3, 4)]
    assert all(QualityFlag.FORWARD_FILLED in flags(t) for t in result.ticks[:3])
    assert result.filled == 3
    assert result.issues[0].detail == "3 minutes 10:01–10:03"


def test_gap_longer_than_limit_is_left_open(validator: Validator) -> None:
    run(validator, [make_tick()])
    later = T0 + timedelta(hours=2)
    result = run(validator, [make_tick(later)], ts=later, feed_heven=120000)
    assert len(result.ticks) == 1
    assert result.issues[0].action == "left_open"


def test_gap_fill_skips_closed_market_minutes(validator: Validator) -> None:
    close = datetime(2026, 9, 26, 12, 28, tzinfo=TEHRAN)
    run(validator, [make_tick(close)])
    after = close + timedelta(minutes=5)  # 12:33, after the close
    result = run(validator, [make_tick(after)], ts=after, feed_heven=123300)
    filled = [
        t.ts.strftime("%H:%M") for t in result.ticks if QualityFlag.FORWARD_FILLED in flags(t)
    ]
    assert filled == ["12:29", "12:30"]


# --- feed ------------------------------------------------------------------------------------


def test_frozen_feed_is_detected(validator: Validator) -> None:
    results = [
        run(validator, [make_tick(T0 + timedelta(minutes=m))], ts=T0 + timedelta(minutes=m))
        for m in range(5)
    ]
    stale = [QualityFlag.STALE_QUOTE in flags(r.ticks[-1]) for r in results]
    assert stale == [False, False, False, True, True]
    logged = [c for r in results for c in checks(r) if c is Check.FEED_STALE]
    assert len(logged) == 1  # edge-triggered


# --- state -------------------------------------------------------------------------------------


def test_warm_start_restores_previous_ticks(validator: Validator) -> None:
    validator.warm(T0.date(), [make_tick(volume=5_000)])
    t1 = T0 + timedelta(minutes=1)
    result = run(validator, [make_tick(t1)], ts=t1)
    assert result.ticks[0].volume == 5_000  # decrease detected against warmed state


def test_issue_rows_match_log_columns(validator: Validator) -> None:
    result = run(validator, [make_tick(last_price=150_000, high_price=150_000)])
    issue = result.issues[0]
    row = dict(zip(issue.columns(), issue.as_row(), strict=True))
    assert row["check"] == "price_out_of_band"
    assert row["severity"] == "error"
    assert replace(issue, detail="x").detail == "x"


def test_warm_start_does_not_relog_ongoing_conditions(validator: Validator) -> None:
    stale = make_tick(quality_flags=int(QualityFlag.NAV_STALE), nav_at=T0 - timedelta(hours=18))
    validator.warm(T0.date(), [stale])
    t1 = T0 + timedelta(minutes=1)
    result = run(validator, [make_tick(t1, nav_at=T0 - timedelta(hours=18))], ts=t1)
    assert QualityFlag.NAV_STALE in flags(result.ticks[0])
    assert Check.NAV_STALE not in checks(result)
