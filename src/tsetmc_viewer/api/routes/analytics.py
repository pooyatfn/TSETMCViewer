"""Analytics endpoints consumed by the panel. All responses are tick-cached."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from tsetmc_viewer.analytics.models import (
    CalendarDay,
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
from tsetmc_viewer.api.cache import cached_json
from tsetmc_viewer.api.deps import Analytics, Bus, ClickHouse, Clock, SessionDay
from tsetmc_viewer.domain.jalali import to_jalali
from tsetmc_viewer.storage.repository import quality_report

router = APIRouter(prefix="/api/v1", tags=["analytics"])
InsCode = Annotated[str, Path(pattern=r"^\d{1,20}$", description="TSETMC instrument code")]


@router.get("/overview", response_model=Overview)
async def overview(
    request: Request, day: SessionDay, analytics: Analytics, bus: Bus, clock: Clock
) -> Response:
    """Headline figures of the session: AUM, money flow, premium, breadth."""
    return await cached_json(
        request, route="overview", params={"day": day}, bus=bus, clock=clock,
        compute=lambda: analytics.overview(day),
    )  # fmt: skip


@router.get("/funds", response_model=list[FundSnapshot])
async def funds(
    request: Request, day: SessionDay, analytics: Analytics, bus: Bus, clock: Clock
) -> Response:
    """Latest state of every equity fund, largest first."""
    return await cached_json(
        request, route="funds", params={"day": day}, bus=bus, clock=clock,
        compute=lambda: analytics.snapshot(day),
    )  # fmt: skip


@router.get("/funds/{ins_code}", response_model=FundDetail)
async def fund_detail(
    request: Request,
    ins_code: InsCode,
    day: SessionDay,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    days: Annotated[int, Query(ge=5, le=4000, description="history window, calendar days")] = 120,
) -> Response:
    """One fund: latest snapshot, returns and daily history of the last ``days`` days."""

    async def compute() -> FundDetail:
        detail = await analytics.fund_detail(ins_code, day, days)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown fund or no data for this day")
        return detail

    return await cached_json(
        request, route="fund", params={"ins": ins_code, "day": day, "days": days},
        bus=bus, clock=clock,
        compute=compute,
    )  # fmt: skip


@router.get("/funds/{ins_code}/intraday", response_model=list[FundIntradayPoint])
async def fund_intraday(
    request: Request,
    ins_code: InsCode,
    day: SessionDay,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
) -> Response:
    """Minute series of price, NAV, premium and individual money flow."""
    return await cached_json(
        request, route="fund_intraday", params={"ins": ins_code, "day": day}, bus=bus,
        clock=clock, compute=lambda: analytics.fund_intraday(ins_code, day),
    )  # fmt: skip


@router.get("/market/flow", response_model=list[MarketFlowPoint])
async def market_flow(
    request: Request, day: SessionDay, analytics: Analytics, bus: Bus, clock: Clock
) -> Response:
    """Cumulative individual net flow into all equity funds, per minute, with the index."""
    return await cached_json(
        request, route="market_flow", params={"day": day}, bus=bus, clock=clock,
        compute=lambda: analytics.market_flow(day),
    )  # fmt: skip


@router.get("/flows/daily", response_model=list[DailyFlow])
async def daily_flows(
    request: Request,
    day: SessionDay,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    days: Annotated[int, Query(ge=5, le=400)] = 60,
) -> Response:
    """Official daily individual net flow per fund type (+ today's live estimate)."""
    return await cached_json(
        request, route="daily_flows", params={"day": day, "days": days}, bus=bus, clock=clock,
        compute=lambda: analytics.daily_flows(day, days),
    )  # fmt: skip


@router.get("/returns", response_model=list[FundReturns])
async def returns(
    request: Request, day: SessionDay, analytics: Analytics, bus: Bus, clock: Clock
) -> Response:
    """1D / 1W / 1M / 3M / YTD price returns per fund (YTD from 1 Farvardin)."""
    return await cached_json(
        request, route="returns", params={"day": day}, bus=bus, clock=clock,
        compute=lambda: analytics.returns(day),
    )  # fmt: skip


@router.get("/risk", response_model=list[FundRisk])
async def risk_return(
    request: Request,
    day: SessionDay,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    days: Annotated[int, Query(ge=20, le=400)] = 90,
) -> Response:
    """Annualised volatility vs. price return per fund over the trailing window."""
    return await cached_json(
        request, route="risk_return", params={"day": day, "days": days}, bus=bus, clock=clock,
        compute=lambda: analytics.risk_return(day, days),
    )  # fmt: skip


@router.get("/quality", tags=["ops"])
async def quality(
    request: Request, day: SessionDay, client: ClickHouse, bus: Bus, clock: Clock
) -> Response:
    """Data-quality report of the session (docs/04)."""

    async def compute() -> dict[str, object]:
        return asdict(await quality_report(client, day))

    return await cached_json(
        request, route="quality", params={"day": day}, bus=bus, clock=clock, compute=compute
    )


@router.get("/premium/daily", response_model=list[PremiumPoint])
async def premium_daily(
    request: Request,
    day: SessionDay,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    days: Annotated[int, Query(ge=5, le=400)] = 120,
) -> Response:
    """Market NAV premium at each session's close: median fund and net-assets-weighted."""
    return await cached_json(
        request, route="premium_daily", params={"day": day, "days": days}, bus=bus, clock=clock,
        compute=lambda: analytics.premium_daily(day, days),
    )  # fmt: skip


@router.get("/premium/intraday", response_model=list[PremiumPoint])
async def premium_intraday(
    request: Request, day: SessionDay, analytics: Analytics, bus: Bus, clock: Clock
) -> Response:
    """Market NAV premium minute by minute during the session."""
    return await cached_json(
        request, route="premium_intraday", params={"day": day}, bus=bus, clock=clock,
        compute=lambda: analytics.premium_intraday(day),
    )  # fmt: skip


@router.get("/sessions", response_model=list[SessionInfo])
async def sessions(
    request: Request,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    limit: Annotated[int, Query(ge=1, le=400)] = 90,
) -> Response:
    """Sessions the panel's date picker can select, newest first."""
    return await cached_json(
        request, route="sessions", params={"limit": limit}, bus=bus, clock=clock,
        compute=lambda: analytics.sessions(limit),
    )  # fmt: skip


@router.get("/calendar", response_model=list[CalendarDay])
async def calendar(
    request: Request,
    analytics: Analytics,
    bus: Bus,
    clock: Clock,
    year: Annotated[int | None, Query(ge=1400, le=1500, description="Jalali year")] = None,
) -> Response:
    """Non-trading weekdays of a Jalali year: official holidays, extra and observed closures."""
    jy = year or to_jalali(clock.now().date())[0]
    return await cached_json(
        request, route="calendar", params={"year": jy}, bus=bus, clock=clock,
        compute=lambda: analytics.calendar(jy),
    )  # fmt: skip
