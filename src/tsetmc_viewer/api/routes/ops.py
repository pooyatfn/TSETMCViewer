"""Operational endpoints: liveness and pipeline status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from fastapi import APIRouter, Query, Request, Response, status

from tsetmc_viewer import __version__, telemetry
from tsetmc_viewer.api.deps import ClickHouse, Clock
from tsetmc_viewer.clock import MarketClock

router = APIRouter(tags=["ops"])


@router.get("/health")
@router.get(
    "/api/v1/health", include_in_schema=False
)  # same, reachable through the panel's /api proxy
async def health(
    client: ClickHouse, clock: Clock, request: Request, response: Response
) -> dict[str, Any]:
    """API liveness (HTTP status) plus the collector's freshness (body only).

    Only the database decides the status code: the compose healthcheck of ``api`` uses
    it, and a stalled collector must not take the panel down with it.
    """
    try:
        db_ok = bool(await client.ping())
    except Exception:
        db_ok = False
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    body: dict[str, Any] = {
        "status": "ok" if db_ok else "degraded",
        "clickhouse": db_ok,
        "version": __version__,
    }
    if db_ok:
        stale_after = getattr(request.app.state, "stale_after_seconds", 180)
        body["collector"] = await _collector_status(client, clock.now(), clock, stale_after)
    return body


async def _collector_status(
    client: AsyncClient, now: datetime, clock: MarketClock, stale_after: int
) -> dict[str, Any]:
    """``ok`` / ``stale`` while the market is open, ``idle`` while it is closed."""
    result = await client.query(
        "SELECT tick, finished_at, status FROM collection_runs ORDER BY started_at DESC LIMIT 10"
    )
    rows = result.result_rows
    market_open = clock.is_open(now)
    if not rows:
        return {"state": "stale" if market_open else "idle", "last_run": None}
    tick, finished_at, last_status = rows[0]
    lag = (now - finished_at).total_seconds()
    streak = next((i for i, r in enumerate(rows) if r[2] != "failed"), len(rows))
    state = "idle" if not market_open else ("ok" if lag <= stale_after else "stale")
    return {
        "state": state,
        "last_run": {"tick": tick, "finished_at": finished_at, "status": last_status},
        "lag_seconds": round(lag),
        "failed_streak": streak,
    }


@router.get("/api/v1/pipeline/runs")
async def recent_runs(
    client: ClickHouse, limit: int = Query(20, ge=1, le=500)
) -> list[dict[str, Any]]:
    """Most recent collector cycles, newest first."""
    result = await client.query(
        "SELECT run_id, tick, status, requests, failed, "
        "dateDiff('millisecond', started_at, finished_at) AS duration_ms "
        "FROM collection_runs ORDER BY started_at DESC LIMIT {limit:UInt32}",
        parameters={"limit": limit},
    )
    return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus exposition. Not proxied by nginx: only Prometheus on the compose network."""
    body, content_type = telemetry.render()
    return Response(content=body, media_type=content_type)
