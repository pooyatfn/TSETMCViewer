"""Per-row data-quality flags, stored as a bitmask in ``fund_ticks.quality_flags``.

A bitmask keeps the tick table narrow while letting queries filter cheaply,
e.g. ``WHERE bitAnd(quality_flags, 2) = 0`` excludes ticks without a NAV. The
bit values are part of the storage contract: never renumber, only append.
"""

from __future__ import annotations

from enum import IntFlag, StrEnum


class QualityFlag(IntFlag):
    NONE = 0
    NAV_MISSING = 1 << 1  # ETF endpoint failed or returned no NAV
    NAV_STALE = 1 << 2  # NAV timestamp older than the staleness threshold
    CLIENT_TYPE_MISSING = 1 << 3  # instrument absent from ClientTypeAll
    FLOW_VALUE_ESTIMATED = 1 << 4  # rial flows = volume × VWAP (no official value intraday)
    NO_TRADES = 1 << 5  # no trade yet today; prices are the reference price
    PRICE_OUT_OF_RANGE = 1 << 6  # price outside the daily allowed band
    CUMULATIVE_DECREASE = 1 << 7  # cumulative volume/value went down
    FORWARD_FILLED = 1 << 8  # row carried forward from the previous tick
    STALE_QUOTE = 1 << 9  # the whole market-watch feed stopped updating
    CLIENT_VOLUME_MISMATCH = 1 << 10  # Σ individual+institutional buys ≠ traded volume
    NAV_CARRIED = 1 << 11  # NAV missing this tick, previous NAV carried forward
    NAV_JUMP = 1 << 12  # NAV moved more than the plausibility threshold between ticks
    RANGE_REPAIRED = 1 << 13  # high/low recomputed to contain open/last

    def names(self) -> list[str]:
        return [f.name for f in QualityFlag if f and f in self and f.name]


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Check(StrEnum):
    """Names written to ``data_quality_log.check``."""

    MISSING_FUND = "missing_fund"
    GAP = "gap"
    PRICE_OUT_OF_BAND = "price_out_of_band"
    OHLC_INCONSISTENT = "ohlc_inconsistent"
    CUMULATIVE_DECREASE = "cumulative_decrease"
    CLIENT_VOLUME_MISMATCH = "client_volume_mismatch"
    NAV_MISSING = "nav_missing"
    NAV_STALE = "nav_stale"
    NAV_JUMP = "nav_jump"
    FEED_STALE = "feed_stale"
