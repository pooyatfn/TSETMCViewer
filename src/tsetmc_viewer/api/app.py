"""HTTP API consumed by the web panel."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from clickhouse_connect.driver.exceptions import OperationalError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from tsetmc_viewer import __version__, telemetry
from tsetmc_viewer.analytics.service import AnalyticsService
from tsetmc_viewer.api.routes import analytics, ops, stream
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import Settings, get_settings
from tsetmc_viewer.logs import configure_logging
from tsetmc_viewer.storage.clickhouse import create_client
from tsetmc_viewer.storage.tickbus import TickBus

log = logging.getLogger(__name__)


async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """ClickHouse unreachable/timed out: a clear, retryable 503 instead of a 500 + traceback.

    Query errors (bad SQL = a bug) are not caught here and stay 500s.
    """
    log.warning("database unavailable", extra={"path": request.url.path, "error": str(exc)[:200]})
    telemetry.API_DB_UNAVAILABLE.inc()
    return JSONResponse(
        {"detail": "database unavailable, retry shortly"},
        status_code=503,
        headers={"Retry-After": "10"},
    )


async def measure(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Count and time every request by *route template* (bounded label values)."""
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        telemetry.API_REQUESTS.labels(route, request.method, str(status)).inc()
        if not route.endswith("/stream"):  # SSE stays open for minutes: not a latency
            telemetry.API_SECONDS.labels(route).observe(time.perf_counter() - started)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:  # built by a uvicorn worker process: set up its logging too
        settings = get_settings()
        configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.clock = MarketClock(settings.market)
        app.state.ch = await create_client(settings.clickhouse)
        app.state.analytics = AnalyticsService(app.state.ch, app.state.clock)
        app.state.bus = TickBus.from_url(settings.redis_url)
        app.state.stale_after_seconds = 3 * settings.collect_interval_seconds
        try:
            yield
        finally:
            await app.state.bus.close()
            await app.state.ch.close()

    app = FastAPI(
        title="TSETMC Viewer API",
        version=__version__,
        description="Live analytics of Iranian equity ETFs. Docs: /docs (Swagger), /redoc.",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Tick", "X-Cache"],
    )
    app.add_exception_handler(OperationalError, database_unavailable)
    app.middleware("http")(measure)
    app.include_router(ops.router)
    app.include_router(analytics.router)
    app.include_router(stream.router)
    return app
