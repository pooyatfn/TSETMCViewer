"""Prometheus metrics of the collector and the API (docs/11-monitoring.md).

One module so every metric name, label and bucket is defined — and reviewed — in
one place. Label values are always bounded (endpoint names, statuses, route
templates), never instrument codes or raw URLs, to keep cardinality small.

The API may run several worker processes (ADR 0010). prometheus_client then needs
``PROMETHEUS_MULTIPROC_DIR`` set *before* this module is imported; gauges declare
how their per-process values combine (``multiprocess_mode``).
"""

from __future__ import annotations

import os
from typing import Final

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

from tsetmc_viewer import __version__

MULTIPROC_ENV: Final = "PROMETHEUS_MULTIPROC_DIR"

# --- build ----------------------------------------------------------------------------------
BUILD_INFO = Gauge(
    "tsetmc_build_info", "Always 1; labels carry the version.", ["version"],
    multiprocess_mode="max",
)  # fmt: skip
BUILD_INFO.labels(version=__version__).set(1)

# --- collector ------------------------------------------------------------------------------
CYCLES = Counter("tsetmc_collector_cycles_total", "Collection cycles by outcome.", ["status"])
CYCLE_SECONDS = Histogram(
    "tsetmc_collector_cycle_duration_seconds",
    "Wall time of one collection cycle (fetch + validate + write).",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 20, 30, 45, 60),
)
FUNDS_EXPECTED = Gauge("tsetmc_collector_funds_expected", "Funds in today's universe.")
FUNDS_RECEIVED = Gauge("tsetmc_collector_funds_received", "Funds written by the last cycle.")
LAST_SUCCESS = Gauge(
    "tsetmc_collector_last_success_timestamp_seconds",
    "Unix time of the last cycle that wrote data (ok or partial).",
)
FAILED_STREAK = Gauge("tsetmc_collector_failed_streak", "Consecutive failed cycles.")
QUALITY_ISSUES = Counter(
    "tsetmc_collector_quality_issues_total",
    "Validator events by check and pipeline action (docs/04-data-quality.md).",
    ["check", "action"],
)
ROWS_REPAIRED = Counter(
    "tsetmc_collector_rows_repaired_total", "Rows fixed by preprocessing.", ["kind"]
)
MARKET_OPEN = Gauge(
    "tsetmc_market_open", "1 while the calendar says the market is open (holidays included)."
)
SESSION_CONFIRMED = Gauge(
    "tsetmc_session_confirmed", "1 once TSETMC shows trades for today (session guard)."
)
LEADER = Gauge("tsetmc_collector_leader", "1 if this replica holds the collector lease.")
HISTORY_ROWS = Counter("tsetmc_history_rows_total", "Official daily history rows written.")
BACKFILL_FUNDS = Counter(
    "tsetmc_backfill_funds_total",
    "Funds processed by the intraday backfill, by decision (ADR 0012).",
    ["status"],
)

# --- data sources (collector) ----------------------------------------------------------------
SOURCE_REQUESTS = Counter(
    "tsetmc_source_requests_total",
    "Requests to data providers by final outcome (after retries).",
    ["source", "endpoint", "outcome"],
)
SOURCE_SECONDS = Histogram(
    "tsetmc_source_request_duration_seconds",
    "Latency of one HTTP attempt to a data provider.",
    ["source", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30),
)
SOURCE_RETRIES = Counter(
    "tsetmc_source_retries_total", "Retried attempts to data providers.", ["source", "endpoint"]
)

# --- API --------------------------------------------------------------------------------------
API_REQUESTS = Counter(
    "tsetmc_api_requests_total", "HTTP requests by route template and status.",
    ["route", "method", "status"],
)  # fmt: skip
API_SECONDS = Histogram(
    "tsetmc_api_request_duration_seconds",
    "HTTP request latency by route template.",
    ["route"],
    buckets=(0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
API_CACHE = Counter(
    "tsetmc_api_cache_total", "Response cache outcomes (hit, miss, shared, not_modified).",
    ["result"],
)  # fmt: skip
API_DB_UNAVAILABLE = Counter(
    "tsetmc_api_database_unavailable_total", "Requests answered 503 because ClickHouse was down."
)
SSE_CLIENTS = Gauge(
    "tsetmc_api_sse_clients", "Open live-update (SSE) connections.", multiprocess_mode="livesum"
)


# --- alert relay ------------------------------------------------------------------------------
ALERTS_RELAYED = Counter(
    "tsetmc_alerts_relayed_total", "Alert notifications delivered by channel and outcome.",
    ["channel", "outcome"],
)  # fmt: skip


def render() -> tuple[bytes, str]:
    """Exposition payload: this process, or all worker processes in multiprocess mode."""
    if os.environ.get(MULTIPROC_ENV):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
