# ADR 0002 — Python 3.12 with asyncio, httpx, and FastAPI

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 1</span></div>

!!! abstract "Summary"
    The bottleneck is network, not CPU. asyncio handles hundreds of concurrent requests in a single thread with precise rate control. FastAPI and Pydantic keep the same typed model from the collector through to the API.

## Context

The collector's work is almost entirely **I/O-bound**: more than 100 HTTP requests per minute, most of the time spent waiting on the network. The financial computations are lightweight. The API also needs to send several concurrent queries to ClickHouse.

## Decision

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Data/finance ecosystem; modern typing (`Self`, `match`). |
| Concurrency | `asyncio` | 120 concurrent requests in a single thread, with a `Semaphore` for rate control. |
| HTTP | `httpx.AsyncClient` | Async, connection pooling, `MockTransport`/`respx` for testing. |
| Retry | In-house implementation (≈30 lines) | Exponential backoff with full jitter; only for transient errors (timeout, 429, 5xx). The `tenacity` dependency wasn't needed for this amount of code. |
| Validation | Pydantic v2 | Parses responses with aliases for TSETMC's field names; settings via `pydantic-settings`. |
| API | FastAPI | Async, automatic OpenAPI (`/docs`), dependency injection for testability. |
| ClickHouse | `clickhouse-connect` (async) | Official client, HTTP protocol, columnar inserts. |
| Package management | `uv` + `uv.lock` | Deterministic, fast installs; the Docker layer stays cached until the lock changes. |
| Code quality | `ruff` (lint + format), `mypy --strict`, `pytest` | One fast tool for lint and format; strict typing from the start. |

## Rejected Options

- **Go**: would have given a faster collector, but the bottleneck is network, not CPU. Financial analysis and pandas are more comfortable in Python.
- **`requests` + threads**: workable for 120 requests, but timeout handling, cancellation, and concurrency limits are cleaner in asyncio.
- **Celery / Airflow**: overkill for "one job per minute" (ADR 0004).
- **Django**: its ORM doesn't fit ClickHouse, and we don't need admin or auth.

## Consequences

- All I/O code must be async. A single blocking call slows down the whole loop (the `ASYNC` ruff rule helps catch this).
- `mypy --strict` has an upfront cost, but pays off in the technical interview and in maintenance.
