"""Official daily history: backfill once, refresh after every close.

Two TSETMC endpoints per fund are merged by date into ``fund_history_daily``:
daily prices (``GetClosingPriceDailyList``) and official individual/
institutional flows with rial values (``GetClientTypeHistory``).

Unlike intraday data, history can be fetched again at any time, so its raw
responses are not archived in ``raw_snapshots`` (each is ~1 MB; ADR 0003's
rationale — unrecoverable data — does not apply).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Protocol

from tsetmc_viewer import telemetry
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.sources.http import SourceError
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import (
    ClientTypeDailyRow,
    DailyPriceRow,
    PayloadError,
    parse_client_type_history,
    parse_daily_prices,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One row of ``fund_history_daily``. Field order == insert column order."""

    trade_date: date
    ins_code: str
    open_price: int
    high_price: int
    low_price: int
    close_price: int
    last_price: int
    prev_close: int
    volume: int
    value: int
    trade_count: int
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
    updated_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, n) for n in self.columns()]


class HistoryStore(Protocol):
    async def insert_history(self, rows: Sequence[HistoryRow]) -> int: ...


def _date(deven: int) -> date:
    y, md = divmod(deven, 10000)
    return date(y, *divmod(md, 100))


def merge_history(
    ins_code: str,
    prices: Iterable[DailyPriceRow],
    flows: Iterable[ClientTypeDailyRow],
    *,
    days: int,
    updated_at: datetime,
) -> list[HistoryRow]:
    """Join prices and flows on the trading date; keep the newest ``days`` trading days.

    A day with prices but no flow row keeps zero flows (and is still useful for
    returns); a flow row without prices is dropped (no trading day).
    """
    by_day = {f.deven: f for f in flows}
    newest = sorted((p for p in prices if p.deven > 0 and p.volume >= 0), key=lambda p: -p.deven)
    rows: list[HistoryRow] = []
    for p in newest[:days]:
        f = by_day.get(p.deven)
        rows.append(
            HistoryRow(
                trade_date=_date(p.deven),
                ins_code=ins_code,
                open_price=p.open_price,
                high_price=p.high_price,
                low_price=p.low_price,
                close_price=p.close_price,
                last_price=p.last_price,
                prev_close=p.prev_close,
                volume=p.volume,
                value=p.value,
                trade_count=p.trade_count,
                ind_buy_volume=f.ind_buy_volume if f else 0,
                ind_sell_volume=f.ind_sell_volume if f else 0,
                inst_buy_volume=f.inst_buy_volume if f else 0,
                inst_sell_volume=f.inst_sell_volume if f else 0,
                ind_buy_value=f.ind_buy_value if f else 0,
                ind_sell_value=f.ind_sell_value if f else 0,
                inst_buy_value=f.inst_buy_value if f else 0,
                inst_sell_value=f.inst_sell_value if f else 0,
                ind_buy_count=f.ind_buy_count if f else 0,
                ind_sell_count=f.ind_sell_count if f else 0,
                inst_buy_count=f.inst_buy_count if f else 0,
                inst_sell_count=f.inst_sell_count if f else 0,
                updated_at=updated_at,
            )
        )
    return rows


@dataclass(frozen=True, slots=True)
class HistoryReport:
    funds: int
    rows: int
    failed: list[str]


class HistorySync:
    def __init__(self, tsetmc: TsetmcClient, store: HistoryStore, clock: MarketClock) -> None:
        self._tsetmc = tsetmc
        self._store = store
        self._clock = clock

    async def _one(self, fund: FundRef, days: int) -> list[HistoryRow]:
        prices_raw, flows_raw = await asyncio.gather(
            self._tsetmc.daily_history(fund.ins_code),
            self._tsetmc.client_type_history(fund.ins_code),
        )
        if not prices_raw.ok:
            raise SourceError(f"daily history HTTP {prices_raw.status_code}")
        prices = parse_daily_prices(prices_raw.json())
        flows = parse_client_type_history(flows_raw.json()) if flows_raw.ok else []
        return merge_history(fund.ins_code, prices, flows, days=days, updated_at=self._clock.now())

    async def sync(self, funds: Iterable[FundRef], *, days: int) -> HistoryReport:
        funds = list(funds)
        results = await asyncio.gather(*(self._one(f, days) for f in funds), return_exceptions=True)
        rows: list[HistoryRow] = []
        failed: list[str] = []
        for fund, result in zip(funds, results, strict=True):
            if isinstance(result, (SourceError, PayloadError, ValueError)):
                failed.append(fund.symbol or fund.ins_code)
                log.warning(
                    "history failed", extra={"ins_code": fund.ins_code, "error": str(result)}
                )
            elif isinstance(result, BaseException):
                raise result
            else:
                rows.extend(result)
        written = await self._store.insert_history(rows)
        telemetry.HISTORY_ROWS.inc(written)
        log.info(
            "history synced", extra={"funds": len(funds), "rows": written, "failed": len(failed)}
        )
        return HistoryReport(len(funds), written, failed)
