# Testing, CI, and Resilience

<p class="lead">This page explains how we know the service works correctly and how it behaves when something breaks: what is tested and why, what CI checks on every change, how the service behaves against TSETMC, ClickHouse, and Redis outages, and what the load test showed about caching.</p>

<div class="kpis">
  <div class="kpi"><b>236</b><span>automated tests (212 Python, 16 panel, 8 alert scenarios)</span></div>
  <div class="kpi"><b>89%</b><span>Python branch coverage (85% minimum required)</span></div>
  <div class="kpi"><b>4</b><span>CI jobs on every push and PR</span></div>
  <div class="kpi"><b>×7</b><span>API throughput with caching, in the load test</span></div>
</div>

## Testing Strategy

Three principles, each born from a real problem in this project:

<div class="grid cards two" markdown>

-   :material-file-download-outline: __Real responses, not fabricated data__

    ---

    Tests run against **real recorded TSETMC responses** (`tests/fixtures/sample`), which `respx` serves at the same real URLs. The real shape of these responses (empty fields, secondary boards, funds with no NAV) is exactly what the pipeline has to handle.

-   :material-database-check-outline: __Real ClickHouse, not a mock__

    ---

    12 integration tests run against a real ClickHouse instance in a disposable database: migrations, materialized views, `FINAL`, replay, and analytical queries. The migration 0004 bug ([ADR 0005](adr/0005-migrations.md)) only showed up on a real database.

-   :material-clock-check-outline: __Injectable time__

    ---

    No code calls `datetime.now()` directly: everything asks `MarketClock`. Tests pin the clock: "Thursday at 10", "Saturday mid-session", "after close". Calendar-dependent behavior (bootstrap, closing snapshot, collector health) is tested deterministically this way.

-   :material-bug-check-outline: __Every bug, a test__

    ---

    Every problem found in real operation was first reproduced with a test and then fixed: converting the index change to a percentage, the migration on 24.8.14, zero net assets in the closing snapshot, and the cache stampede (below).

</div>

### Test Map

| Layer | Files | What it guarantees |
|---|---|---|
| Financial and domain logic | `test_metrics`, `test_domain`, `test_clock` | Premium/discount, net assets, money flow, buyer strength, Jalali calendar, market hours |
| Parsing and transformation | `test_tsetmc_models`, `test_transform`, `test_universe` | Real responses convert correctly into models. Fund identity and primary board are correctly identified |
| Data quality | `test_validate` (20 tests) | All 10 checks, every remediation method, edge-triggered event logging, and state recovery after a restart |
| Collection | `test_collector`, `test_bootstrap`, `test_collector_loop`, `test_history`, `test_http` | Full cycle, partial and total failure, retry, startup outside market hours, clean shutdown, consecutive-failure alerting |
| Storage | `test_migrate` and the integration tests | Migrations are idempotent, locked by checksum, and run against real ClickHouse in both tuple-naming modes |
| API | `test_api`, `test_api_cache`, `test_analytics_api`, `test_stream` | Response contracts, ETag and 304, single-flight, per-tick session-date memoization, SSE, 503 error handling |
| Configuration | `test_repo_consistency` | The ClickHouse tag is the same in CI and compose. Every code setting is documented in `.env.example` |
| Panel | `format.test.ts`, `options.test.ts` | Persian formatting of numbers and signs, and chart display decisions (leveraged funds, edge cases, color, left-to-right time) |

!!! tip "Two tests that prevent "file inconsistency""
    `test_repo_consistency.py` doesn't test the product's code, it tests **consistency between files**. The first time it ran, it immediately caught four settings that existed in code but not in `.env.example`. The second test guarantees that CI runs the tests against the same ClickHouse version the user runs.

## CI

<figure class="diagram">
<img src="assets/diagrams/ci-pipeline.svg" alt="CI stages: one event, three parallel jobs, and one smoke test">
<figcaption>Figure 1 — Every push and PR has three parallel jobs. The smoke test only runs once the Python code and the panel are healthy, since building the images is the most expensive stage.</figcaption>
</figure>

The smoke test is the most important part of CI: it brings up the whole system exactly as the user runs it (`docker compose up`) and checks it from the outside. The day-5 migration bug was exactly this kind: all unit tests were green, and only `docker compose up` revealed it. The collector doesn't run in CI, because TSETMC isn't reachable from servers outside Iran. Its behavior is tested with recorded responses.

<div class="grid cards two" markdown>

-   :material-lock-check-outline: __Everything from the lockfile__

    ---

    `uv sync --frozen` and `npm ci`: CI installs exactly the same versions that were on the developer's machine. The pre-commit hooks also run ruff, mypy, and tsc from the same lockfiles, so a hook and CI can never disagree about which ruff version to use.

-   :material-timer-sand: __Fast feedback__

    ---

    Jobs run in parallel, and the uv and npm caches are enabled. If a new push lands on the same branch, the previous run is canceled (`concurrency`).

</div>

## Resilience

The table below shows how the service behaves against each kind of failure. The general principle is: **a failure in one component must not take down the healthy ones, and it must never be silent.**

| Failure | Behavior | Where it's visible |
|---|---|---|
| TSETMC is unreachable (VPN on, IP blocked) | The cycle is recorded with status `failed` and the loop keeps going. After 3 consecutive failed cycles, **one** error is logged with a "VPN?" hint (not one error per minute), and a "recovered" message on return | collector log, the `collector` section of `/health` |
| One endpoint is partially broken (e.g., a fund's NAV) | The fund's row is written with the `NAV_MISSING` flag, and the cycle status is `partial` | The data-quality card in the panel |
| ClickHouse is down | The API returns **503** with `Retry-After: 10`, not a 500 and a traceback. A SQL error (a bug) still returns 500 | The panel shows an error message and retries on the next tick |
| Redis is down | Caching and events are disabled (fail-open). The API reads directly from ClickHouse | A warning in the log ([ADR 0006](adr/0006-caching.md)) |
| The collector loop is stuck | The heartbeat file misses the deadline it set for itself, and the Docker healthcheck becomes `unhealthy` | `docker compose ps` |
| `docker stop` mid-cycle | The SIGTERM signal only interrupts the sleep between cycles. The current cycle finishes writing completely (30-second grace period), and then the process exits | The `collector stopped` log |
| Startup after market close | History is completed and a closing snapshot is taken of the last session ([ADR 0004](adr/0004-scheduling.md#day-5-review-startup-outside-market-hours)) | The panel isn't empty |

### Two Kinds of Health, Deliberately Separate {#two-kinds-of-health-are-deliberately-separate}

<div class="grid cards two" markdown>

-   :material-heart-pulse: __Loop liveness (Docker)__

    ---

    `tsetmc-viewer healthcheck` only asks: "has the loop kept its promise?" Before every sleep or cycle, the loop writes the next heartbeat deadline to a file. A TSETMC outage does **not** make the loop unhealthy, because restarting the container wouldn't fix it.

-   :material-chart-timeline-variant: __Data freshness (API)__

    ---

    `/health` reports the collector's status in the response body: `ok`, `stale`, or `idle`, along with the lag and the number of consecutive failures. The HTTP status code depends only on the database, because the `web` service waits for `api` to be healthy, and a broken collector shouldn't take the panel down too.

</div>

```console
$ curl -s localhost:8000/health | jq
{
  "status": "ok",
  "clickhouse": true,
  "version": "0.1.0",
  "collector": {
    "state": "stale",
    "last_run": {"tick": "…T10:41:00+03:30", "finished_at": "…", "status": "failed"},
    "lag_seconds": 312,
    "failed_streak": 5
  }
}
```

## Load Test {#load-test}

`scripts/loadtest.py` creates several virtual users, each requesting the dashboard's six endpoints back-to-back and continuously, like a browser. Results are on real data (159 funds and 400 days of history), one uvicorn process, and 2 CPU cores, **with ClickHouse and the load generator on the same machine**:

<figure class="diagram">
<img src="assets/diagrams/load-test.svg" alt="Load test results: throughput and response time across three caching modes">
<figcaption>Figure 2 — With caching, throughput improves 6 to 7x and response time improves about 10x. In ETag mode, the browser gets a bodyless 304 response.</figcaption>
</figure>

| Mode | 1 user: median / p95 | 20 users: throughput | 20 users: median / p95 |
|---|---|---|---|
| No cache (`REDIS_URL=`) | 37 / 66 ms | 49 requests/second | 372 / 671 ms |
| Redis cache | 4.4 / 9.5 ms | 283 requests/second | 44 / 214 ms |
| Redis and ETag | 2.9 / 4.6 ms | 349 requests/second | 34 / 169 ms |

One panel refresh is six requests. So a single API process on this same modest hardware, with caching, refreshes about **3500 open panels** per minute, and the load on ClickHouse is **independent of the number of users**: each key is computed only once per tick.

### Two Load-Test Findings That Changed the Code

??? bug "1. Cache stampede"
    On the first run with 20 users, 56 requests were cache misses, not 6. When a new tick arrives, every open panel wants the same keys at the same instant, and they all hit ClickHouse together. This repeated **every minute**.

    **Fix:** in `api/cache.py`, computing missing keys became *single-flight*: the first request computes, and the rest wait for that same result (`X-Cache: shared`). If the computation errors, everyone waiting gets the same error, and nothing is cached. Result: 6 computations instead of 56. Test: `test_concurrent_misses_compute_once`.

??? bug "2. A hidden query on every request"
    Even cached and 304 responses took about 11 to 14 milliseconds. The cause was that the "latest session" (the default for `?date=`) was being queried from ClickHouse on every request, **before** it even reached the cache.

    **Fix:** the latest session only changes with a new tick, so it's memoized in memory per tick (for at most a minute). The tick number itself is also read from Redis only once. Result: cached response time went from 14.5 → 4.4 ms, and 304 from 11.4 → 2.9 ms. With both fixes, cached-mode throughput went from 132 to 283 requests/second. Test: `test_session_date_is_memoised_per_tick`.

```bash
# repeat the test (API on :8000, once with REDIS_URL= and once with Redis)
uv run python scripts/loadtest.py --users 20 --seconds 20 --mode plain
uv run python scripts/loadtest.py --users 20 --seconds 20 --mode etag
```

## Cleanup

- The FIPIRAN client, written on day 1 and unused after day 2, was removed ([Data Sources](02-data-sources.md)). Code that doesn't run doesn't get tested either, but a reader of the code still has to make sense of it.
- The YAML-check pre-commit hook was failing on `mkdocs.yml` (because of the `!!python` tag), blocking every developer's commit. Now it only checks syntax. Recorded API responses and font files were excluded from the formatting hooks so they stay byte-for-byte untouched.
- `uv sync` (i.e., `make install`) now also installs the docs tooling (`default-groups`). Without it, `make docs` failed on a fresh clone. The service image is built with `--no-default-groups`, so dev and docs tooling never end up in the production image.
