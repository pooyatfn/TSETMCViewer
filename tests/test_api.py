from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from clickhouse_connect.driver.exceptions import OperationalError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import TEHRAN
from tsetmc_viewer.api.app import database_unavailable
from tsetmc_viewer.api.deps import get_analytics, get_bus, get_clickhouse, get_clock
from tsetmc_viewer.api.routes import analytics, ops
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.config import MarketSettings
from tsetmc_viewer.storage.tickbus import TickBus

OPEN = datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN)  # Saturday 10:00
CLOSED = datetime(2026, 9, 24, 10, 0, tzinfo=TEHRAN)  # Thursday


class FixedClock(MarketClock):
    def __init__(self, now: datetime) -> None:
        super().__init__(MarketSettings())
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeClickHouse:
    def __init__(self, healthy: bool, runs: list[tuple[Any, ...]] | None = None) -> None:
        self.healthy = healthy
        self.runs = runs or []

    async def ping(self) -> bool:
        return self.healthy

    async def query(self, sql: str, parameters: Any = None) -> Any:
        return type("R", (), {"result_rows": self.runs, "column_names": []})()


def make_client(
    healthy: bool, runs: list[tuple[Any, ...]] | None = None, now: datetime = OPEN
) -> TestClient:
    app = FastAPI()  # no lifespan: no real database needed
    app.include_router(ops.router)
    app.dependency_overrides[get_clickhouse] = lambda: FakeClickHouse(healthy, runs)
    app.dependency_overrides[get_clock] = lambda: FixedClock(now)
    return TestClient(app)


def run(minutes_ago: float, status: str = "ok", now: datetime = OPEN) -> tuple[Any, ...]:
    finished = now - timedelta(minutes=minutes_ago)
    return (finished.replace(second=0), finished, status)


def test_health_ok_with_fresh_collector() -> None:
    resp = make_client(True, [run(0.5)]).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["collector"]["state"] == "ok"
    assert body["collector"]["lag_seconds"] == 30


def test_stale_collector_is_reported_but_keeps_the_api_healthy() -> None:
    runs = [run(10, "failed"), run(11, "failed"), run(12, "ok")]
    resp = make_client(True, runs).get("/health")
    assert resp.status_code == 200  # the panel must stay up
    collector = resp.json()["collector"]
    assert collector["state"] == "stale"
    assert collector["failed_streak"] == 2


def test_collector_is_idle_when_the_market_is_closed() -> None:
    resp = make_client(True, [run(60 * 20, now=CLOSED)], now=CLOSED).get("/health")
    assert resp.json()["collector"]["state"] == "idle"


def test_health_is_also_served_under_the_api_prefix() -> None:
    """The panel only reaches /api/* through nginx."""
    assert make_client(True, [run(0.5)]).get("/api/v1/health").json()["collector"]["state"] == "ok"


def test_health_degraded_returns_503() -> None:
    resp = make_client(False).get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "clickhouse": False, "version": "0.1.0"}


class DownAnalytics:
    async def session_date(self) -> Any:
        raise OperationalError("connection refused")


def test_database_outage_is_a_retryable_503() -> None:
    app = FastAPI()
    app.add_exception_handler(OperationalError, database_unavailable)
    app.include_router(analytics.router)
    app.dependency_overrides[get_analytics] = lambda: DownAnalytics()
    app.dependency_overrides[get_bus] = lambda: TickBus(None)
    resp = TestClient(app).get("/api/v1/overview")
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "10"
    assert resp.json() == {"detail": "database unavailable, retry shortly"}
