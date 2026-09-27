"""Per-cycle validation and preprocessing of fund ticks (docs/04-data-quality.md).

The validator is the only stateful stage of the pipeline: several checks
compare a tick with the same fund's previous tick (cumulative counters must
not decrease, NAV must not jump, gaps must be filled). That state lives here,
is reset every trading day, and is warmed from ClickHouse when the collector
restarts mid-session.

Design rules
- **Never silent.** Every repair sets a bit in ``quality_flags`` *and* writes a
  ``data_quality_log`` row naming the action taken.
- **Repair only with information we have.** Carry the last known value
  forward; never interpolate or invent trades.
- **Edge-triggered logging** for persistent conditions (stale NAV, missing
  fund): one log row when the condition starts, not one per minute. The flag
  is still set on every affected tick.
- **Domain rules over generic statistics.** The exchange enforces a daily
  price band, so "outlier" means "outside the band", not "3 sigma".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, fields, replace
from datetime import date, datetime, timedelta
from uuid import UUID

from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import ValidationSettings
from tsetmc_viewer.domain.quality import Check, QualityFlag, Severity
from tsetmc_viewer.pipeline.transform import FundTick, TickBatch

_CUMULATIVE = (
    "volume",
    "value",
    "trade_count",
    "ind_buy_volume",
    "ind_sell_volume",
    "inst_buy_volume",
    "inst_sell_volume",
)
_MINUTE = timedelta(minutes=1)
# Persistent conditions that are logged once per episode, and the flag that marks them.
_EDGE_FLAGS = (
    (QualityFlag.NAV_STALE, Check.NAV_STALE),
    (QualityFlag.NAV_MISSING, Check.NAV_MISSING),
    (QualityFlag.CLIENT_VOLUME_MISMATCH, Check.CLIENT_VOLUME_MISMATCH),
    (QualityFlag.STALE_QUOTE, Check.FEED_STALE),
)


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """One row of ``data_quality_log``."""

    ts: datetime
    run_id: UUID
    ins_code: str
    check: Check
    severity: Severity
    action: str
    detail: str

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [self.ts, self.run_id, self.ins_code, str(self.check), str(self.severity),
                self.action, self.detail]  # fmt: skip


@dataclass(slots=True)
class ValidationResult:
    ticks: list[FundTick] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    filled: int = 0  # rows created by forward-filling (gaps and missing funds)
    repaired: int = 0  # rows whose values were changed

    def count(self, check: Check) -> int:
        return sum(1 for i in self.issues if i.check is check)


class _Cycle:
    """Accumulates issues for one validation call; applies edge-triggering."""

    def __init__(self, validator: Validator, ts: datetime, run_id: UUID) -> None:
        self._v = validator
        self.ts = ts
        self.run_id = run_id
        self.result = ValidationResult()

    def report(
        self,
        ins: str,
        check: Check,
        severity: Severity,
        action: str,
        detail: str = "",
        *,
        edge: bool = False,
    ) -> None:
        if edge:
            key = (ins, check)
            if key in self._v._active:
                return
            self._v._active.add(key)
        self.result.issues.append(
            QualityIssue(self.ts, self.run_id, ins, check, severity, action, detail)
        )

    def clear(self, ins: str, check: Check) -> None:
        self._v._active.discard((ins, check))


class Validator:
    def __init__(self, settings: ValidationSettings, clock: MarketClock) -> None:
        self._s = settings
        self._clock = clock
        self._day: date | None = None
        self._last: dict[str, FundTick] = {}
        self._active: set[tuple[str, Check]] = set()
        self._feed_heven = 0
        self._feed_unchanged = 0

    @property
    def day(self) -> date | None:
        return self._day

    def warm(self, day: date, last_ticks: Iterable[FundTick]) -> None:
        """Start ``day`` with the latest stored tick of each fund (after a restart)."""
        self._reset(day)
        self._last = {t.ins_code: t for t in last_ticks if t.ts.date() == day}
        # Restore edge-trigger state so a restart does not re-log ongoing conditions.
        for t in self._last.values():
            flags = QualityFlag(t.quality_flags)
            for flag, check in _EDGE_FLAGS:
                if flag in flags:
                    self._active.add(("" if check is Check.FEED_STALE else t.ins_code, check))

    def _reset(self, day: date) -> None:
        self._day = day
        self._last = {}
        self._active = set()
        self._feed_heven = 0
        self._feed_unchanged = 0

    # --- entry point -------------------------------------------------------------
    def validate(
        self, batch: TickBatch, *, ts: datetime, run_id: UUID, ingested_at: datetime
    ) -> ValidationResult:
        if self._day != ts.date():
            self._reset(ts.date())
        cycle = _Cycle(self, ts, run_id)
        feed_stale = self._feed_is_stale(batch, cycle)

        for tick in batch.ticks:
            prev = self._last.get(tick.ins_code)
            if prev is not None:
                self._fill_gap(prev, ts, ingested_at, cycle)
            checked = self._check(tick, prev, batch.bands.get(tick.ins_code), feed_stale, cycle)
            cycle.result.ticks.append(checked)
            self._last[tick.ins_code] = checked
            cycle.clear(tick.ins_code, Check.MISSING_FUND)

        for ins in batch.missing:
            self._fill_missing(ins, ts, run_id, ingested_at, cycle)
        return cycle.result

    # --- feed-level ------------------------------------------------------------------
    def _feed_is_stale(self, batch: TickBatch, cycle: _Cycle) -> bool:
        if not batch.ticks or batch.feed_heven <= 0:
            return False
        if batch.feed_heven == self._feed_heven:
            self._feed_unchanged += 1
        else:
            self._feed_heven, self._feed_unchanged = batch.feed_heven, 0
        stale = self._feed_unchanged >= self._s.feed_stale_cycles
        if stale:
            cycle.report(
                "",
                Check.FEED_STALE,
                Severity.ERROR,
                "flagged",
                f"market watch unchanged for {self._feed_unchanged} cycles "
                f"(hEven={batch.feed_heven})",
                edge=True,
            )
        else:
            cycle.clear("", Check.FEED_STALE)
        return stale

    # --- completeness ----------------------------------------------------------------
    def _carry(self, prev: FundTick, ts: datetime, run_id: UUID, ingested_at: datetime) -> FundTick:
        return replace(
            prev,
            ts=ts,
            run_id=run_id,
            ingested_at=ingested_at,
            quality_flags=prev.quality_flags | QualityFlag.FORWARD_FILLED,
        )

    def _fill_gap(self, prev: FundTick, ts: datetime, ingested_at: datetime, cycle: _Cycle) -> None:
        """Minutes between the previous tick and now (collector down, failed cycles)."""
        if ts - prev.ts <= _MINUTE or prev.ts.date() != ts.date():
            return
        minutes = [
            prev.ts + _MINUTE * k
            for k in range(1, int((ts - prev.ts) / _MINUTE))
            if self._clock.is_open(prev.ts + _MINUTE * k)
        ]
        if not minutes:
            return
        if len(minutes) > self._s.max_gap_fill_minutes:
            cycle.report(
                prev.ins_code,
                Check.GAP,
                Severity.ERROR,
                "left_open",
                f"{len(minutes)} minutes since {prev.ts:%H:%M} exceed the fill limit",
            )
            return
        for m in minutes:
            cycle.result.ticks.append(self._carry(prev, m, cycle.run_id, ingested_at))
        cycle.result.filled += len(minutes)
        cycle.report(
            prev.ins_code,
            Check.GAP,
            Severity.WARN,
            "forward_filled",
            f"{len(minutes)} minutes {minutes[0]:%H:%M}–{minutes[-1]:%H:%M}",
        )

    def _fill_missing(
        self, ins: str, ts: datetime, run_id: UUID, ingested_at: datetime, cycle: _Cycle
    ) -> None:
        prev = self._last.get(ins)
        fresh = prev is not None and ts - prev.ts <= _MINUTE * self._s.max_gap_fill_minutes
        if prev is None or not fresh:
            cycle.report(
                ins, Check.MISSING_FUND, Severity.ERROR, "dropped", "no recent tick", edge=True
            )
            return
        filled = self._carry(prev, ts, run_id, ingested_at)
        cycle.result.ticks.append(filled)
        cycle.result.filled += 1
        self._last[ins] = filled
        cycle.report(
            ins, Check.MISSING_FUND, Severity.WARN, "forward_filled", "absent from market watch",
            edge=True,
        )  # fmt: skip

    # --- per tick ------------------------------------------------------------------------
    def _check(
        self,
        tick: FundTick,
        prev: FundTick | None,
        band: tuple[int, int] | None,
        feed_stale: bool,
        cycle: _Cycle,
    ) -> FundTick:
        ins = tick.ins_code
        flags = QualityFlag(tick.quality_flags)
        changes: dict[str, object] = {}
        same_day = prev is not None and prev.ts.date() == tick.ts.date()

        # 1. Price band enforced by the exchange.
        if band and tick.trade_count > 0:
            lo, hi = band
            for name in ("last_price", "close_price"):
                price = getattr(tick, name)
                if not lo <= price <= hi:
                    flags |= QualityFlag.PRICE_OUT_OF_RANGE
                    action = "kept"
                    if same_day and prev is not None and lo <= getattr(prev, name) <= hi:
                        changes[name] = getattr(prev, name)
                        action = "replaced_with_previous"
                    cycle.report(
                        ins, Check.PRICE_OUT_OF_BAND, Severity.ERROR, action,
                        f"{name}={price} outside [{lo}, {hi}]",
                    )  # fmt: skip

        # 2. OHLC consistency: high/low must contain open and last.
        if tick.trade_count > 0:
            last = int(changes.get("last_price", tick.last_price))  # type: ignore[call-overload]
            points = [p for p in (tick.open_price, last, tick.high_price, tick.low_price) if p > 0]
            hi_ok, lo_ok = max(points), min(points)
            if (hi_ok, lo_ok) != (tick.high_price, tick.low_price):
                changes |= {"high_price": hi_ok, "low_price": lo_ok}
                flags |= QualityFlag.RANGE_REPAIRED
                cycle.report(
                    ins, Check.OHLC_INCONSISTENT, Severity.WARN, "recomputed",
                    f"high/low {tick.high_price}/{tick.low_price} → {hi_ok}/{lo_ok}",
                )  # fmt: skip

        # 3. Cumulative counters never decrease within a day.
        if same_day and prev is not None:
            decreased = [n for n in _CUMULATIVE if getattr(tick, n) < getattr(prev, n)]
            if decreased:
                changes |= {n: getattr(prev, n) for n in decreased}
                flags |= QualityFlag.CUMULATIVE_DECREASE
                cycle.report(
                    ins, Check.CUMULATIVE_DECREASE, Severity.ERROR, "kept_previous",
                    ", ".join(f"{n} {getattr(prev, n)}→{getattr(tick, n)}" for n in decreased),
                )  # fmt: skip

        # 4. Individual + institutional buys (and sells) must add up to traded volume.
        if QualityFlag.CLIENT_TYPE_MISSING not in flags and tick.volume > 0:
            buys = tick.ind_buy_volume + tick.inst_buy_volume
            sells = tick.ind_sell_volume + tick.inst_sell_volume
            off = max(abs(buys - tick.volume), abs(sells - tick.volume)) / tick.volume
            if off > self._s.client_mismatch_ratio:
                flags |= QualityFlag.CLIENT_VOLUME_MISMATCH
                cycle.report(
                    ins, Check.CLIENT_VOLUME_MISMATCH, Severity.WARN, "flagged",
                    f"buys={buys} sells={sells} volume={tick.volume}", edge=True,
                )  # fmt: skip
            else:
                cycle.clear(ins, Check.CLIENT_VOLUME_MISMATCH)

        # 5. NAV: carry forward when missing, then staleness and plausibility.
        if tick.nav_redemption is None:
            if prev is not None and prev.nav_redemption is not None:
                changes |= {
                    "nav_redemption": prev.nav_redemption,
                    "nav_subscription": prev.nav_subscription,
                    "nav_at": prev.nav_at,
                }
                flags |= QualityFlag.NAV_CARRIED
                action = "carried_forward"
            else:
                action = "none"
            cycle.report(ins, Check.NAV_MISSING, Severity.WARN, action, edge=True)
        else:
            cycle.clear(ins, Check.NAV_MISSING)
            if prev is not None and prev.nav_redemption:
                jump = abs(tick.nav_redemption / prev.nav_redemption - 1)
                if jump > self._s.nav_jump_ratio:
                    flags |= QualityFlag.NAV_JUMP
                    cycle.report(
                        ins, Check.NAV_JUMP, Severity.WARN, "flagged",
                        f"{prev.nav_redemption}→{tick.nav_redemption} ({jump:.1%})",
                    )  # fmt: skip

        nav_at = changes.get("nav_at", tick.nav_at)
        if isinstance(nav_at, datetime):
            age = tick.ts - nav_at
            if age > timedelta(minutes=self._s.nav_stale_minutes):
                flags |= QualityFlag.NAV_STALE
                cycle.report(
                    ins, Check.NAV_STALE, Severity.INFO, "flagged",
                    f"NAV from {nav_at:%Y-%m-%d %H:%M}", edge=True,
                )  # fmt: skip
            else:
                cycle.clear(ins, Check.NAV_STALE)

        # 6. Whole feed frozen.
        if feed_stale:
            flags |= QualityFlag.STALE_QUOTE

        if changes:
            cycle.result.repaired += 1
        return replace(tick, **changes, quality_flags=int(flags))  # type: ignore[arg-type]
