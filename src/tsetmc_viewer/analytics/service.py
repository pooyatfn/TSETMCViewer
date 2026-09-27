"""Analytics service: SQL retrieves, Python computes (docs/05-financial-logic.md).

Retrieval stays in ClickHouse (FINAL / LIMIT 1 BY / argMaxIf over at most a
few hundred thousand rows), while every financial formula lives in
``domain.metrics`` where it is unit-tested. The result sets handed to Python
are small: one row per fund (~160) or one row per minute (~210).
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient

from tsetmc_viewer.analytics.models import (
    CalendarDay,
    DailyBar,
    DailyFlow,
    FundDetail,
    FundIntradayPoint,
    FundReturns,
    FundRisk,
    FundSnapshot,
    MarketFlowPoint,
    Overview,
    PremiumPoint,
    SessionInfo,
)
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.domain import metrics
from tsetmc_viewer.domain.funds import FundType
from tsetmc_viewer.domain.jalali import format_jalali, from_jalali, jalali_year_start
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.domain.status import StatusKind, status_kind


def observed_note(rows: list[dict[str, Any]], day: date) -> str | None:
    return next((str(r["note"]) for r in rows if r["day"] == day), None)


_EQUITY = tuple(t.value for t in FundType if t.is_equity)

_SNAPSHOT_SQL = """
SELECT t.ins_code AS ins_code, f.symbol AS symbol, f.name AS name, f.fund_type AS fund_type,
       t.ts AS ts, t.last_price AS last_price, t.close_price AS close_price,
       t.prev_close AS prev_close, t.nav_redemption AS nav, t.nav_at AS nav_at,
       t.value AS value, t.volume AS volume, t.trade_count AS trade_count,
       t.block_value AS block_value,
       t.ind_buy_value AS ind_buy_value, t.ind_sell_value AS ind_sell_value,
       t.inst_buy_value AS inst_buy_value, t.inst_sell_value AS inst_sell_value,
       t.ind_buy_count AS ind_buy_count, t.ind_sell_count AS ind_sell_count,
       t.quality_flags AS quality_flags, u.units AS units
FROM (
    SELECT * FROM fund_ticks FINAL
    WHERE toDate(ts) = {day:Date} {fund_filter}
    ORDER BY ts DESC LIMIT 1 BY ins_code
) AS t
LEFT JOIN (SELECT * FROM funds FINAL) AS f ON f.ins_code = t.ins_code
LEFT JOIN (
    -- Units as of the day; if none were recorded yet (a closing snapshot of an earlier
    -- session, taken after today's universe sync), the nearest later count.
    SELECT ins_code,
           if(countIf(trade_date <= {day:Date}) > 0,
              argMaxIf(units, trade_date, trade_date <= {day:Date}),
              argMinIf(units, trade_date, trade_date > {day:Date})) AS units
    FROM fund_daily FINAL GROUP BY ins_code
) AS u ON u.ins_code = t.ins_code
"""


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(zip(result.column_names, r, strict=True)) for r in result.result_rows]


def _flags(value: int) -> list[str]:
    return QualityFlag(value).names()


class AnalyticsService:
    def __init__(self, client: AsyncClient, clock: MarketClock) -> None:
        self._ch = client
        self._clock = clock

    async def _query(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        return _rows(await self._ch.query(sql, parameters=params))

    # --- session ------------------------------------------------------------------------
    async def session_date(self) -> date | None:
        """The latest trading day with data: today while trading, else the last session."""
        rows = await self._query(
            "SELECT greatest((SELECT max(toDate(ts)) FROM fund_ticks),"
            " (SELECT max(trade_date) FROM fund_history_daily)) AS d"
        )
        d = rows[0]["d"] if rows else None
        return d if d and d.year > 1970 else None

    async def sessions(self, limit: int = 90) -> list[SessionInfo]:
        """Days the panel can actually show (``fund_ticks`` has at least a closing snapshot).

        Newest first. ``has_intraday`` tells the picker whether that day has more than
        one recorded minute, so it can explain a flat intraday chart instead of looking broken.
        """
        rows = await self._query(
            "SELECT toDate(ts) AS d, uniqExact(ts) AS minutes FROM fund_ticks"
            " GROUP BY d ORDER BY d DESC LIMIT {limit:UInt32}",
            limit=limit,
        )
        return [
            SessionInfo(day=r["d"], day_fa=format_jalali(r["d"]), has_intraday=r["minutes"] > 1)
            for r in rows
        ]

    # --- snapshot -------------------------------------------------------------------------
    async def snapshot(self, day: date, ins_code: str | None = None) -> list[FundSnapshot]:
        fund_filter = "AND ins_code = {ins:String}" if ins_code else ""
        rows = await self._query(
            _SNAPSHOT_SQL.replace("{fund_filter}", fund_filter), day=day, ins=ins_code or ""
        )
        snaps: list[FundSnapshot] = []
        for r in rows:
            fund_type = FundType(r["fund_type"]) if r["fund_type"] else FundType.OTHER
            units = int(r["units"]) if r["units"] else None
            net_assets = metrics.aum(r["nav"], units)
            snaps.append(
                FundSnapshot(
                    ins_code=r["ins_code"],
                    symbol=r["symbol"] or r["ins_code"],
                    name=r["name"] or "",
                    fund_type=fund_type,
                    fund_type_fa=fund_type.label_fa,
                    ts=r["ts"],
                    last_price=r["last_price"],
                    close_price=r["close_price"],
                    prev_close=r["prev_close"],
                    change=metrics.pct_change(r["close_price"], r["prev_close"]),
                    nav=r["nav"],
                    nav_at=r["nav_at"],
                    premium=metrics.nav_premium(r["close_price"], r["nav"], fund_type),
                    units=units,
                    aum=net_assets,
                    share_of_aum=None,
                    value=r["value"],
                    volume=r["volume"],
                    trade_count=r["trade_count"],
                    block_value=r["block_value"],
                    ind_net_flow=metrics.net_flow(r["ind_buy_value"], r["ind_sell_value"]),
                    inst_net_flow=metrics.net_flow(r["inst_buy_value"], r["inst_sell_value"]),
                    buyer_power=metrics.buyer_power(
                        r["ind_buy_value"],
                        r["ind_buy_count"],
                        r["ind_sell_value"],
                        r["ind_sell_count"],
                    ),
                    turnover=metrics.turnover(r["value"], net_assets),
                    quality_flags=_flags(r["quality_flags"]),
                )
            )
        total = sum(s.aum or 0 for s in snaps)
        states = await self._states(day, ins_code)
        for s in snaps:
            s.share_of_aum = s.aum / total if s.aum and total else None
            if st := states.get(s.ins_code):
                s.status_kind = status_kind(st["code"])
                s.status_title = st["title"] or st["code"]
                s.status_at = st["at"]
                s.under_supervision = bool(st["supervision"])
        return sorted(snaps, key=lambda s: -(s.aum or 0))

    async def _states(self, day: date, ins_code: str | None) -> dict[str, dict[str, Any]]:
        """Latest known trading status of each fund as of ``day`` (looks back 30 days)."""
        fund_filter = "AND ins_code = {ins:String}" if ins_code else ""
        rows = await self._query(
            f"""
            SELECT ins_code, argMax(code, ts) AS code, argMax(title, ts) AS title,
                   argMax(under_supervision, ts) AS supervision, max(ts) AS at
            FROM fund_state
            WHERE toDate(ts) BETWEEN {{day:Date}} - 30 AND {{day:Date}} {fund_filter}
            GROUP BY ins_code
            """,
            day=day,
            ins=ins_code or "",
        )
        return {r["ins_code"]: r for r in rows}

    # --- overview -----------------------------------------------------------------------------
    async def overview(self, day: date) -> Overview:
        snaps = await self.snapshot(day)
        market = await self._query(
            "SELECT index_value, index_change FROM market_ticks FINAL "
            "WHERE toDate(ts) = {day:Date} ORDER BY ts DESC LIMIT 1",
            day=day,
        )
        runs = await self._query(
            "SELECT sum(received_funds) AS r, sum(expected_funds) AS e FROM collection_runs "
            "WHERE toDate(tick) = {day:Date}",
            day=day,
        )
        premiums = [s.premium for s in snaps]
        now = self._clock.now()
        return Overview(
            session_date=day,
            session_date_fa=format_jalali(day),
            last_update=max((s.ts for s in snaps), default=None),
            is_live=day == now.date() and self._clock.is_open(now),
            funds=len(snaps),
            total_aum=sum(s.aum or 0 for s in snaps),
            total_value=sum(s.value for s in snaps),
            ind_net_flow=sum(s.ind_net_flow for s in snaps),
            median_premium=metrics.robust_center(premiums),
            weighted_premium=metrics.weighted_mean((sn.premium, sn.aum) for sn in snaps),
            at_premium=sum(1 for p in premiums if p is not None and p > 0),
            at_discount=sum(1 for p in premiums if p is not None and p < 0),
            advancers=sum(1 for s in snaps if (s.change or 0) > 0),
            decliners=sum(1 for s in snaps if (s.change or 0) < 0),
            unchanged=sum(1 for s in snaps if not s.change),
            index_value=market[0]["index_value"] if market else None,
            index_change=_index_change_ratio(market[0]) if market else None,
            not_trading=sum(
                s.status_kind not in (StatusKind.OPEN, StatusKind.UNKNOWN) for s in snaps
            ),
            completeness=(runs[0]["r"] / runs[0]["e"]) if runs and runs[0]["e"] else None,
            holiday_today=await self._holiday_today(now),
        )

    async def _holiday_today(self, now: datetime) -> str | None:
        """Official/extra holiday from the calendar, or a closure the collector observed."""
        rows = await self._query(
            "SELECT trading, note FROM market_calendar FINAL WHERE day = {d:Date}", d=now.date()
        )
        if rows:
            return None if rows[0]["trading"] else str(rows[0]["note"])
        return self._clock.holiday(now)

    # --- calendar -------------------------------------------------------------------------------
    async def calendar(self, jalali_year: int) -> list[CalendarDay]:
        """Every non-trading weekday of a Jalali year, plus observed corrections."""
        cal = self._clock.calendar
        observed = await self._query("SELECT day, trading, note FROM market_calendar FINAL")
        cal.load_observed((r["day"], bool(r["trading"]), r["note"]) for r in observed)
        start, end = from_jalali(jalali_year, 1, 1), from_jalali(jalali_year + 1, 1, 1)
        days = sorted({*cal.official(jalali_year), *(r["day"] for r in observed)})
        out: list[CalendarDay] = []
        for d in days:
            if not start <= d < end:
                continue
            st = cal.status(d)
            if st.source == "weekend":
                continue
            out.append(
                CalendarDay(
                    day=d,
                    day_fa=format_jalali(d),
                    trading=st.trading,
                    reason=st.reason or (observed_note(observed, d) if st.trading else None),
                    source=st.source,
                )
            )
        return out

    # --- market premium -------------------------------------------------------------------------
    async def _units_asof(self) -> dict[str, list[tuple[date, int]]]:
        rows = await self._query(
            "SELECT ins_code, trade_date, units FROM fund_daily FINAL ORDER BY trade_date"
        )
        units: dict[str, list[tuple[date, int]]] = {}
        for r in rows:
            units.setdefault(r["ins_code"], []).append((r["trade_date"], int(r["units"])))
        return units

    @staticmethod
    def _units_on(series: list[tuple[date, int]] | None, day: date) -> int | None:
        """Units as of ``day``; before the first record, the earliest one (see snapshot)."""
        if not series:
            return None
        i = bisect_right([d for d, _ in series], day)
        return series[i - 1][1] if i else series[0][1]

    @staticmethod
    def _premium_point(
        at: datetime | date, rows: list[tuple[FundType, int, int | None, int | None]]
    ) -> PremiumPoint:
        """rows: (type, close, nav, units) per fund; leveraged funds drop out via nav_premium."""
        pairs = [
            (metrics.nav_premium(close, nav, ft), metrics.aum(nav, units))
            for ft, close, nav, units in rows
        ]
        defined = [p for p, _ in pairs if p is not None]
        return PremiumPoint(
            at=at,
            at_fa=format_jalali(at.date() if isinstance(at, datetime) else at),
            median=metrics.robust_center(list(defined)),
            weighted=metrics.weighted_mean(pairs),
            funds=len(defined),
        )

    async def premium_daily(self, day: date, days: int = 120) -> list[PremiumPoint]:
        """Market premium at each session's close, from the live data's end-of-day rollup.

        TSETMC publishes no NAV history, so this series starts on the first day the
        collector (or a closing snapshot) recorded and grows by one point per session.
        """
        rows = await self._query(
            """
            SELECT e.trade_date AS d, e.ins_code AS ins, any(f.fund_type) AS fund_type,
                   argMaxMerge(e.close_price) AS close, argMaxMerge(e.nav_redemption) AS nav
            FROM fund_eod AS e
            INNER JOIN (SELECT ins_code, fund_type FROM funds FINAL
                        WHERE fund_type IN {equity:Array(String)}) AS f
                ON f.ins_code = e.ins_code
            WHERE e.trade_date > {day:Date} - {days:UInt32} AND e.trade_date <= {day:Date}
            GROUP BY d, ins
            ORDER BY d
            """,
            day=day,
            days=days,
            equity=list(_EQUITY),
        )
        units = await self._units_asof()
        by_day: dict[date, list[tuple[FundType, int, int | None, int | None]]] = {}
        for r in rows:
            by_day.setdefault(r["d"], []).append(
                (
                    FundType(r["fund_type"]),
                    r["close"],
                    r["nav"],
                    self._units_on(units.get(r["ins"]), r["d"]),
                )
            )
        return [self._premium_point(d, group) for d, group in sorted(by_day.items())]

    async def premium_intraday(self, day: date) -> list[PremiumPoint]:
        """Market premium minute by minute during the session."""
        rows = await self._query(
            """
            SELECT t.ts AS ts, t.ins_code AS ins, f.fund_type AS fund_type,
                   t.close_price AS close, t.nav_redemption AS nav
            FROM (SELECT ts, ins_code, close_price, nav_redemption FROM fund_ticks FINAL
                  WHERE toDate(ts) = {day:Date}) AS t
            INNER JOIN (SELECT ins_code, fund_type FROM funds FINAL
                        WHERE fund_type IN {equity:Array(String)}) AS f
                ON f.ins_code = t.ins_code
            ORDER BY ts
            """,
            day=day,
            equity=list(_EQUITY),
        )
        units = await self._units_asof()
        by_ts: dict[datetime, list[tuple[FundType, int, int | None, int | None]]] = {}
        for r in rows:
            by_ts.setdefault(r["ts"], []).append(
                (
                    FundType(r["fund_type"]),
                    r["close"],
                    r["nav"],
                    self._units_on(units.get(r["ins"]), day),
                )
            )
        return [self._premium_point(ts, group) for ts, group in sorted(by_ts.items())]

    # --- intraday -------------------------------------------------------------------------------
    async def market_flow(self, day: date) -> list[MarketFlowPoint]:
        rows = await self._query(
            """
            SELECT t.ts AS ts, t.flow AS flow, t.value AS value, m.index_value AS index_value
            FROM (
                SELECT ts,
                       sum(toInt64(ind_buy_value) - toInt64(ind_sell_value)) AS flow,
                       sum(value) AS value
                FROM fund_ticks FINAL WHERE toDate(ts) = {day:Date} GROUP BY ts
            ) AS t
            LEFT JOIN (SELECT ts, index_value FROM market_ticks FINAL
                       WHERE toDate(ts) = {day:Date}) AS m ON m.ts = t.ts
            ORDER BY ts
            """,
            day=day,
        )
        return [
            MarketFlowPoint(
                ts=r["ts"],
                ind_net_flow=r["flow"],
                value=r["value"],
                index_value=r["index_value"] or None,
            )
            for r in rows
        ]

    async def fund_intraday(self, ins_code: str, day: date) -> list[FundIntradayPoint]:
        rows = await self._query(
            """
            SELECT t.ts AS ts, t.last_price AS last_price, t.close_price AS close_price,
                   t.nav_redemption AS nav, t.volume AS volume, t.quality_flags AS flags,
                   toInt64(t.ind_buy_value) - toInt64(t.ind_sell_value) AS flow,
                   f.fund_type AS fund_type
            FROM (SELECT * FROM fund_ticks FINAL
                  WHERE ins_code = {ins:String} AND toDate(ts) = {day:Date}) AS t
            LEFT JOIN (SELECT * FROM funds FINAL) AS f ON f.ins_code = t.ins_code
            ORDER BY ts
            """,
            ins=ins_code,
            day=day,
        )
        live = [
            FundIntradayPoint(
                ts=r["ts"],
                last_price=r["last_price"],
                close_price=r["close_price"],
                nav=r["nav"],
                premium=metrics.nav_premium(
                    r["close_price"], r["nav"], FundType(r["fund_type"] or "other")
                ),
                ind_net_flow=r["flow"],
                volume=r["volume"],
                quality_flags=_flags(r["flags"]),
            )
            for r in rows
        ]
        return await self._backfilled(ins_code, day, before=live[0].ts if live else None) + live

    async def _backfilled(
        self, ins_code: str, day: date, *, before: datetime | None
    ) -> list[FundIntradayPoint]:
        """Minutes rebuilt from trades (ADR 0012), only where no live tick exists."""
        if before is None:
            return []  # nothing live to anchor to: the backfill only fills gaps before it
        rows = await self._query(
            """
            SELECT ts, last_price, volume
            FROM fund_ticks_backfill FINAL
            WHERE ins_code = {ins:String} AND toDate(ts) = {day:Date}
              AND ts < toDateTime({before:UInt32})
            ORDER BY ts
            """,
            ins=ins_code,
            day=day,
            before=int(before.timestamp()),  # epoch: no time-zone guessing in the driver
        )
        return [
            FundIntradayPoint(
                ts=r["ts"],
                last_price=r["last_price"],
                close_price=r["last_price"],
                nav=None,
                premium=None,
                ind_net_flow=None,
                volume=r["volume"],
                quality_flags=[],
                backfilled=True,
            )
            for r in rows
        ]

    # --- daily ----------------------------------------------------------------------------------
    async def daily_flows(self, day: date, days: int = 60) -> list[DailyFlow]:
        """Official individual net flow per day and fund type, plus today's live estimate."""
        rows = await self._query(
            """
            SELECT h.trade_date AS trade_date, f.fund_type AS fund_type,
                   sum(toInt64(h.ind_buy_value) - toInt64(h.ind_sell_value)) AS flow,
                   sum(h.value) AS value
            FROM (SELECT * FROM fund_history_daily FINAL
                  WHERE trade_date > {day:Date} - {days:UInt32}
                    AND trade_date <= {day:Date}) AS h
            INNER JOIN (SELECT ins_code, fund_type FROM funds FINAL
                        WHERE fund_type IN {equity:Array(String)}) AS f
                ON f.ins_code = h.ins_code
            GROUP BY trade_date, fund_type
            ORDER BY trade_date, fund_type
            """,
            day=day,
            days=days,
            equity=list(_EQUITY),
        )
        flows = [
            DailyFlow(
                trade_date=r["trade_date"],
                trade_date_fa=format_jalali(r["trade_date"]),
                fund_type=FundType(r["fund_type"]),
                ind_net_flow=r["flow"],
                value=r["value"],
                estimated=False,
            )
            for r in rows
        ]
        if not any(f.trade_date == day for f in flows):
            by_type: dict[FundType, list[FundSnapshot]] = {}
            for s in await self.snapshot(day):
                by_type.setdefault(s.fund_type, []).append(s)
            flows += [
                DailyFlow(
                    trade_date=day,
                    trade_date_fa=format_jalali(day),
                    fund_type=t,
                    ind_net_flow=sum(s.ind_net_flow for s in group),
                    value=sum(s.value for s in group),
                    estimated=True,
                )
                for t, group in sorted(by_type.items())
            ]
        return flows

    async def returns(self, day: date) -> list[FundReturns]:
        """Price returns over calendar windows, from official closes (+ today's live close)."""
        ytd = jalali_year_start(day)
        rows = await self._query(
            """
            SELECT h.ins_code AS ins_code, any(f.symbol) AS symbol, any(f.fund_type) AS fund_type,
                   argMax(h.close_price, h.trade_date) AS c0,
                   max(h.trade_date) AS d0,
                   argMaxIf(h.close_price, h.trade_date, h.trade_date < max_d) AS c1d,
                   argMaxIf(h.close_price, h.trade_date, h.trade_date <= {day:Date} - 7) AS c1w,
                   argMaxIf(h.close_price, h.trade_date, h.trade_date <= {day:Date} - 30) AS c1m,
                   argMaxIf(h.close_price, h.trade_date, h.trade_date <= {day:Date} - 91) AS c3m,
                   argMaxIf(h.close_price, h.trade_date, h.trade_date < {ytd:Date}) AS cytd
            FROM (SELECT *, max(trade_date) OVER (PARTITION BY ins_code) AS max_d
                  FROM fund_history_daily FINAL
                  WHERE trade_date <= {day:Date} AND trade_date > {day:Date} - 400
                    AND close_price > 0) AS h
            INNER JOIN (SELECT ins_code, symbol, fund_type FROM funds FINAL
                        WHERE fund_type IN {equity:Array(String)}) AS f
                ON f.ins_code = h.ins_code
            GROUP BY h.ins_code
            """,
            day=day,
            ytd=ytd,
            equity=list(_EQUITY),
        )
        live = {s.ins_code: s for s in await self.snapshot(day)}
        out: list[FundReturns] = []
        for r in rows:
            c0, c1d = r["c0"], r["c1d"]
            snap = live.get(r["ins_code"])
            if snap and r["d0"] < day:  # today's session not in history yet: use live close
                c0, c1d = snap.close_price, snap.prev_close
            out.append(
                FundReturns(
                    ins_code=r["ins_code"],
                    symbol=r["symbol"],
                    fund_type=FundType(r["fund_type"]),
                    r_1d=metrics.pct_change(c0, c1d),
                    r_1w=metrics.pct_change(c0, r["c1w"]),
                    r_1m=metrics.pct_change(c0, r["c1m"]),
                    r_3m=metrics.pct_change(c0, r["c3m"]),
                    r_ytd=metrics.pct_change(c0, r["cytd"]),
                )
            )
        return sorted(out, key=lambda x: x.symbol)

    async def risk_return(self, day: date, days: int = 90) -> list[FundRisk]:
        """Volatility vs. return over the trailing window (docs/10-limitations.md #2).

        One point per equity fund: how bumpy the last ``days`` were (annualised
        stdev of daily returns) against what that ride actually paid (price
        return over the same window). AUM sizes the bubble in the chart.
        """
        rows = await self._query(
            """
            SELECT ins_code, groupArray(close_price) AS closes
            FROM (
                SELECT ins_code, close_price
                FROM fund_history_daily FINAL
                WHERE trade_date <= {day:Date} AND trade_date > {day:Date} - {days:UInt32}
                  AND close_price > 0
                ORDER BY ins_code, trade_date
            )
            GROUP BY ins_code
            """,
            day=day,
            days=days,
        )
        by_ins = {r["ins_code"]: [int(c) for c in r["closes"]] for r in rows}
        out: list[FundRisk] = []
        for snap in await self.snapshot(day):
            if not snap.fund_type.is_equity:
                continue
            closes = by_ins.get(snap.ins_code, [])
            # Today's live close is not in fund_history_daily yet; append it so the
            # window reaches "now" instead of stopping at yesterday's rollup.
            series = [*closes, snap.close_price] if snap.close_price else closes
            period_return = metrics.pct_change(series[-1], series[0]) if len(series) >= 2 else None
            out.append(
                FundRisk(
                    ins_code=snap.ins_code,
                    symbol=snap.symbol,
                    fund_type=snap.fund_type,
                    volatility=metrics.volatility(series),
                    period_return=period_return,
                    aum=snap.aum,
                )
            )
        return sorted(out, key=lambda x: x.symbol)

    async def fund_detail(self, ins_code: str, day: date, days: int = 120) -> FundDetail | None:
        snaps = await self.snapshot(day, ins_code)
        if not snaps:
            return None
        history = await self._query(
            """
            SELECT trade_date, close_price, value,
                   toInt64(ind_buy_value) - toInt64(ind_sell_value) AS flow
            FROM fund_history_daily FINAL
            WHERE ins_code = {ins:String} AND trade_date > {day:Date} - {days:UInt32}
            ORDER BY trade_date
            """,
            ins=ins_code,
            day=day,
            days=days,
        )
        returns = next((r for r in await self.returns(day) if r.ins_code == ins_code), None)
        return FundDetail(
            snapshot=snaps[0],
            returns=returns,
            history=[
                DailyBar(
                    trade_date=h["trade_date"],
                    trade_date_fa=format_jalali(h["trade_date"]),
                    close_price=h["close_price"],
                    value=h["value"],
                    ind_net_flow=h["flow"],
                )
                for h in history
            ],
        )


def _index_change_ratio(row: dict[str, Any]) -> float | None:
    """TSETMC reports the index change in points; the panel speaks in percent."""
    value, change = row["index_value"], row["index_change"]
    prev = value - change
    return change / prev if prev else None
