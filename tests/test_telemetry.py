"""Prometheus metrics: the numbers dashboards and alerts are built on must move."""

from __future__ import annotations

from datetime import datetime

import fakeredis
import httpx
import respx
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from support import ATLAS, BASE, TEHRAN, MemoryStore, mock_tsetmc
from tsetmc_viewer.api.app import measure
from tsetmc_viewer.api.cache import cached_json
from tsetmc_viewer.api.routes import ops
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.tickbus import TickBus


def value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_a_cycle_updates_collector_and_source_metrics(http_settings: HttpSettings) -> None:
    cycles = value("tsetmc_collector_cycles_total", status="partial")
    etf_errors = value(
        "tsetmc_source_requests_total", source="tsetmc", endpoint="etf", outcome="http_5xx"
    )
    retries = value("tsetmc_source_retries_total", source="tsetmc", endpoint="etf")
    clock = MarketClock(MarketSettings())
    store = MemoryStore()
    with respx.mock as router:
        router.get(f"{BASE}/Fund/GetETFByInsCode/{ATLAS}").mock(return_value=httpx.Response(500))
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            universe = FundUniverse(UniverseSync(client, store, clock), store)
            collector = Collector(
                client, store, clock, universe, Validator(ValidationSettings(), clock)
            )
            run = await collector.collect_once(datetime(2026, 9, 26, 10, 0, tzinfo=TEHRAN))

    assert run.status == "partial"
    assert value("tsetmc_collector_cycles_total", status="partial") == cycles + 1
    assert value("tsetmc_collector_funds_received") == run.received_funds
    assert value("tsetmc_collector_last_success_timestamp_seconds") == run.finished_at.timestamp()
    # One NAV request failed after its retries: counted once as an outcome, retries separately.
    assert value(
        "tsetmc_source_requests_total", source="tsetmc", endpoint="etf", outcome="http_5xx"
    ) == etf_errors + 1  # fmt: skip
    assert value("tsetmc_source_retries_total", source="tsetmc", endpoint="etf") > retries


def test_api_metrics_use_route_templates_and_cache_outcomes() -> None:
    bus = TickBus(fakeredis.FakeAsyncRedis())
    app = FastAPI()
    app.middleware("http")(measure)
    app.include_router(ops.router)
    clock = MarketClock(MarketSettings())

    @app.get("/api/v1/things/{ins}")
    async def thing(request: Request, ins: str) -> Response:
        async def compute() -> dict[str, str]:
            return {"ins": ins}

        return await cached_json(
            request, route="thing", params={"ins": ins}, compute=compute, bus=bus, clock=clock
        )

    client = TestClient(app)
    before = value(
        "tsetmc_api_requests_total", route="/api/v1/things/{ins}", method="GET", status="200"
    )
    misses = value("tsetmc_api_cache_total", result="miss")
    client.get("/api/v1/things/1")
    client.get("/api/v1/things/2")
    body = client.get("/metrics").text
    assert (
        value("tsetmc_api_requests_total", route="/api/v1/things/{ins}", method="GET", status="200")
        == before + 2
    )  # fmt: skip — one series for the template, not one per fund
    assert value("tsetmc_api_cache_total", result="miss") == misses + 2
    assert 'route="/api/v1/things/{ins}"' in body
    assert "tsetmc_build_info" in body
