"""Turn one cycle's parsed payloads into fund-level ticks.

Pure functions only (no I/O), so the whole transformation is unit-tested
against recorded TSETMC responses and reused verbatim by ``replay``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields
from datetime import datetime
from uuid import UUID

from tsetmc_viewer.domain.funds import FundRef, is_fund_unit, is_primary_board, isin_stem
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.sources.tsetmc_models import (
    ClientTypeRow,
    EtfNav,
    MarketOverview,
    MarketWatchRow,
)


@dataclass(frozen=True, slots=True)
class FundTick:
    """One row of ``fund_ticks``. Field order == insert column order."""

    ts: datetime
    ins_code: str
    run_id: UUID
    last_price: int
    close_price: int
    open_price: int
    high_price: int
    low_price: int
    prev_close: int
    volume: int
    value: int
    trade_count: int
    block_volume: int
    block_value: int
    nav_redemption: int | None
    nav_subscription: int | None
    nav_at: datetime | None
    bid_price: int
    bid_volume: int
    ask_price: int
    ask_volume: int
    ind_buy_volume: int
    ind_sell_volume: int
    inst_buy_volume: int
    inst_sell_volume: int
    ind_buy_value: int
    ind_sell_value: int
    inst_buy_value: int
    inst_sell_value: int
    ind_buy_count: int
    ind_sell_count: int
    inst_buy_count: int
    inst_sell_count: int
    quality_flags: int
    ingested_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, name) for name in self.columns()]


@dataclass(frozen=True, slots=True)
class MarketTick:
    ts: datetime
    run_id: UUID
    index_value: float
    index_change: float
    eq_index_value: float
    eq_index_change: float
    market_value: float
    state: str
    ingested_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, name) for name in self.columns()]


@dataclass(slots=True)
class TickBatch:
    ticks: list[FundTick] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # expected funds absent from market watch
    # Context the validator needs but that is not stored per tick:
    bands: dict[str, tuple[int, int]] = field(default_factory=dict)  # allowed (min, max) price
    feed_heven: int = 0  # latest instrument update time in the whole market watch (HHMMSS)


@dataclass(frozen=True, slots=True)
class _Board:
    volume: int = 0
    value: int = 0


def _secondary_boards(rows: Iterable[MarketWatchRow]) -> dict[str, _Board]:
    """Sum turnover of non-primary fund boards per ISIN stem."""
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if is_fund_unit(r.isin, r.sector) and not is_primary_board(r.isin):
            a = acc[isin_stem(r.isin)]
            a[0] += r.volume
            a[1] += r.value
    return {stem: _Board(v, val) for stem, (v, val) in acc.items()}


def _vwap(row: MarketWatchRow) -> float:
    """Average traded price today; falls back to the reference price."""
    if row.volume > 0 and row.value > 0:
        return row.value / row.volume
    return float(row.close_price or row.prev_close)


def build_fund_ticks(
    *,
    ts: datetime,
    run_id: UUID,
    ingested_at: datetime,
    universe: Mapping[str, FundRef],
    market_watch: Sequence[MarketWatchRow],
    client_types: Sequence[ClientTypeRow],
    navs: Mapping[str, EtfNav],
) -> TickBatch:
    watch = {r.ins_code: r for r in market_watch}
    clients = {c.ins_code: c for c in client_types}
    boards = _secondary_boards(market_watch)
    batch = TickBatch(feed_heven=max((r.heven for r in market_watch), default=0))

    for ins_code, fund in universe.items():
        row = watch.get(ins_code)
        if row is None:
            batch.missing.append(ins_code)
            continue

        flags = QualityFlag.FLOW_VALUE_ESTIMATED
        nav = navs.get(ins_code)
        if nav is None or nav.redemption <= 0:
            flags |= QualityFlag.NAV_MISSING
            nav = None
        ct = clients.get(ins_code)
        if ct is None:
            flags |= QualityFlag.CLIENT_TYPE_MISSING
        if row.trade_count == 0:
            flags |= QualityFlag.NO_TRADES

        if row.min_allowed > 0 and row.max_allowed > 0:
            batch.bands[ins_code] = (row.min_allowed, row.max_allowed)
        price = _vwap(row)
        board = boards.get(fund.stem, _Board())
        top = row.top

        def est(volume: int, _p: float = price) -> int:
            return round(volume * _p)

        batch.ticks.append(
            FundTick(
                ts=ts,
                ins_code=ins_code,
                run_id=run_id,
                last_price=row.last_price,
                close_price=row.close_price,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.low_price,
                prev_close=row.prev_close,
                volume=row.volume,
                value=row.value,
                trade_count=row.trade_count,
                block_volume=board.volume,
                block_value=board.value,
                nav_redemption=nav.redemption if nav else None,
                nav_subscription=nav.subscription if nav else None,
                nav_at=nav.nav_at if nav else None,
                bid_price=top.bid_price if top else 0,
                bid_volume=top.bid_volume if top else 0,
                ask_price=top.ask_price if top else 0,
                ask_volume=top.ask_volume if top else 0,
                ind_buy_volume=ct.ind_buy_volume if ct else 0,
                ind_sell_volume=ct.ind_sell_volume if ct else 0,
                inst_buy_volume=ct.inst_buy_volume if ct else 0,
                inst_sell_volume=ct.inst_sell_volume if ct else 0,
                ind_buy_value=est(ct.ind_buy_volume) if ct else 0,
                ind_sell_value=est(ct.ind_sell_volume) if ct else 0,
                inst_buy_value=est(ct.inst_buy_volume) if ct else 0,
                inst_sell_value=est(ct.inst_sell_volume) if ct else 0,
                ind_buy_count=ct.ind_buy_count if ct else 0,
                ind_sell_count=ct.ind_sell_count if ct else 0,
                inst_buy_count=ct.inst_buy_count if ct else 0,
                inst_sell_count=ct.inst_sell_count if ct else 0,
                quality_flags=int(flags),
                ingested_at=ingested_at,
            )
        )
    return batch


def build_market_tick(
    *, ts: datetime, run_id: UUID, ingested_at: datetime, overview: MarketOverview
) -> MarketTick:
    return MarketTick(
        ts=ts,
        run_id=run_id,
        index_value=overview.index_value,
        index_change=overview.index_change,
        eq_index_value=overview.eq_index_value,
        eq_index_change=overview.eq_index_change,
        market_value=overview.market_value,
        state=overview.state,
        ingested_at=ingested_at,
    )
