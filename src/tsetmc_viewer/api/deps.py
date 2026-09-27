"""FastAPI dependencies shared by all routers."""

from __future__ import annotations

import time
from datetime import date
from typing import Annotated

from clickhouse_connect.driver.asyncclient import AsyncClient
from fastapi import Depends, HTTPException, Query, Request

from tsetmc_viewer.analytics.service import AnalyticsService
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.storage.tickbus import TickBus


def get_clickhouse(request: Request) -> AsyncClient:
    client: AsyncClient = request.app.state.ch
    return client


def get_analytics(request: Request) -> AnalyticsService:
    service: AnalyticsService = request.app.state.analytics
    return service


def get_bus(request: Request) -> TickBus:
    bus: TickBus = request.app.state.bus
    return bus


def get_clock(request: Request) -> MarketClock:
    clock: MarketClock = request.app.state.clock
    return clock


ClickHouse = Annotated[AsyncClient, Depends(get_clickhouse)]
Analytics = Annotated[AnalyticsService, Depends(get_analytics)]
Bus = Annotated[TickBus, Depends(get_bus)]
Clock = Annotated[MarketClock, Depends(get_clock)]


async def session_day(
    request: Request,
    analytics: Analytics,
    bus: Bus,
    day: Annotated[
        date | None, Query(alias="date", description="YYYY-MM-DD; default: last session")
    ] = None,
) -> date:
    """The requested day, or the latest trading session that has data.

    The latest session can only change when a new tick is committed, so it is
    memoised per tick (and for at most a minute). Without this, every request —
    even a cache hit or a 304 — paid one ClickHouse query (Day 6 load test).
    """
    tick = await bus.current()
    request.state.tick = tick  # reused by cached_json: one Redis round-trip per request
    if day is not None:
        return day
    memo: tuple[str, float, date] | None = getattr(request.app.state, "session_memo", None)
    now = time.monotonic()
    if tick != "none" and memo and memo[0] == tick and now - memo[1] < 60:
        return memo[2]
    latest = await analytics.session_date()
    if latest is None:
        raise HTTPException(status_code=404, detail="no data collected yet")
    if tick != "none":
        request.app.state.session_memo = (tick, now, latest)
    return latest


SessionDay = Annotated[date, Depends(session_day)]
