# Running and Operations

<p class="lead">Installing, running, monitoring, and troubleshooting the service. Everything runs with Docker Compose and comes up on any environment that has Docker.</p>

## Prerequisites

| Tool | Version | For |
|---|---|---|
| Docker Engine | 24+ | Running all services |
| Docker Compose | 2.24+ | Optional `env_file` and conditional `depends_on` |
| [uv](https://docs.astral.sh/uv/) | 0.8+ | Local development only; it installs Python 3.12 itself |

## Networking: VPN and TSETMC {#vpn-and-tsetmc-networking}

!!! danger "The most important operational note for Iran"
    Two restrictions pull in opposite directions. **Building** the image requires international internet access, but **running** it requires an Iranian IP.

| Destination | From inside Iran | With a foreign VPN |
|---|:---:|:---:|
| Docker Hub (images) | :material-close-circle:{ style="color: var(--bad)" } usually blocked | :material-check-circle:{ style="color: var(--ok)" } |
| PyPI and npm (during build) | :material-check-circle:{ style="color: var(--ok)" } sometimes slow | :material-check-circle:{ style="color: var(--ok)" } |
| **TSETMC** | :material-check-circle:{ style="color: var(--ok)" } | :material-close-circle:{ style="color: var(--bad)" } foreign IP is rejected |

```text
1. VPN on  →  docker compose build && docker compose pull
2. VPN off →  docker compose up -d
```

!!! tip "split tunneling"
    If your VPN supports split tunneling, exclude the `tsetmc.com` domain from the tunnel so you don't need to turn the VPN off. If TSETMC is only reachable through an internal proxy, set `HTTPS_PROXY` in `.env`; httpx honors it.

## Running

=== "Docker (recommended)"

    ```bash
    cp .env.example .env            # change the ClickHouse password if needed
    docker compose up -d --build
    docker compose ps               # migrate should be Exited (0)
    curl localhost:8000/health      # {"status":"ok","clickhouse":true,...}
    ```

    | Address | Service |
    |---|---|
    | <http://localhost:8080> | **User panel** (the "Documentation" tab contains a summary of these very docs) |
    | <http://localhost:8000/docs> | Interactive API documentation (Swagger) |
    | <http://localhost:8123/play> | ClickHouse query console |

    **The panel isn't empty from the very first run.** If `collector` starts outside market hours (VPN off), it performs the following on its own:

    1. Loads the official daily history up to the last session: 400 days on an empty database (`HISTORY_MAX_DAYS`), and only the missing days on subsequent runs.
    2. If there is no minute-level data for the last session, it takes a **closing snapshot** of that session, timestamped at that session's closing time.

    This takes about one to two minutes. Watch its progress with `docker compose logs -f collector` (the `bootstrap done` message). To run it manually:

    ```bash
    docker compose run --rm collector bootstrap
    ```

    If the collector starts during market hours, this step is skipped: live cycles start immediately, and history is loaded half an hour after the market closes.

=== "Local development"

    ```bash
    make install                    # uv sync + pre-commit
    docker compose up -d clickhouse migrate
    uv run tsetmc-viewer collect-once
    uv run tsetmc-viewer api --port 8000
    uv run mkdocs serve             # docs on :8000 with live reload
    ```

## Commands

All commands run both via `uv run tsetmc-viewer …` and, in Docker, via `docker compose run --rm collector …`.

| Command | Does |
|---|---|
| `migrate` | Creates the database and applies migrations |
| `sync-funds` | Builds today's fund list and prints it broken down by type |
| `collect` | Continuous loop: syncs before market open and runs one cycle per minute |
| `collect-once` | A single immediate cycle |
| `replay --date 2026-09-26` | Rebuilds `fund_ticks` for one day from `raw_snapshots` (after a parser fix) |
| `quality --date 2026-09-26` | Data-quality report for a day: completeness, flags, and events |
| `bootstrap` | Outside market hours: history up to the last session + a closing snapshot of that session if it has no minute-level data (collector runs this itself on startup) |
| `backfill-intraday` | Rebuilds today's minute bars, from before the collector started, from trade-by-trade data (collector runs this itself after the third cycle; [ADR 0012](adr/0012-intraday-backfill.md)). :warning: VPN off |
| `backfill-sessions [--through DAY] [--days N]` | Rebuilds minute bars for the last `N` trading days (default `SESSION_BACKFILL_DAYS`) up to and including `--through`, from price history (collector runs this itself during bootstrap; [ADR 0013](adr/0013-session-backfill.md)). Prints each `BackfillReport`'s output; `rejected_symbols` shows which funds didn't reconcile with the official figure. :warning: VPN off |
| `backfill --days N` | Reloads the official daily history with a custom window (default `HISTORY_MAX_DAYS`) |
| `api` | Runs the API |
| `healthcheck` | Exit code 0 if the collector loop is alive (Docker healthcheck) |
| `alert-relay` | Delivers Alertmanager alerts to Bale, Telegram, or a webhook |
| `api --workers N` | API with N worker processes (default `API_WORKERS`) |

Outside market hours (Saturday through Wednesday, 9:00 to 12:30) the collector sleeps. To test it:

```bash
make collect-once                                          # a single immediate cycle
COLLECT_IGNORE_MARKET_HOURS=true docker compose up -d collector   # continuous collection
```

## Monitoring

For dashboards and alerting, also bring up the monitoring profile (Grafana at <http://localhost:3000>). Setup, receiving alerts in Bale, and the fix guide for each alert are in [Monitoring and Alerting](11-monitoring.md):

```bash
docker compose --profile monitoring up -d
```

Even without it, the following tools are available:

```bash
docker compose ps                                    # collector: healthy = the loop is alive
curl -s localhost:8000/health | jq .collector        # ok / stale / idle + lag and consecutive failures
make logs                                            # JSON logs from collector and api
curl 'localhost:8000/api/v1/pipeline/runs?limit=10'  # the latest cycles
```

Two kinds of health are deliberately separate ([details](09-quality-engineering.md#two-kinds-of-health-are-deliberately-separate)): "the loop is alive" (Docker) and "data is fresh" (`/health`). After 3 consecutive failed cycles, the collector logs **one** `collector failing` message at ERROR level, and a `collector recovered` message when it recovers.

??? example "Useful ClickHouse queries"

    ```sql
    -- health of cycles in the last hour
    SELECT status, count(), avg(dateDiff('millisecond', started_at, finished_at)) AS avg_ms
    FROM collection_runs WHERE started_at > now() - INTERVAL 1 HOUR GROUP BY status;

    -- latency and error rate per endpoint
    SELECT endpoint, count(), countIf(status_code != 200) AS errors,
           quantile(0.95)(latency_ms) AS p95_ms
    FROM raw_snapshots WHERE fetched_at > now() - INTERVAL 1 DAY GROUP BY endpoint;
    ```

## Calendar and Holidays

- Official holidays for 1405 and each year's solar holidays live in `src/tsetmc_viewer/domain/calendar.py`. See a given year's list via the API: `curl localhost:8000/api/v1/calendar?year=1405`.
- **A holiday announced by the exchange** (e.g., a sudden closure): write `MARKET_EXTRA_HOLIDAYS={"2026-10-05": "reason"}` in `.env` and restart the collector.
- **An unannounced holiday:** you don't need to do anything. If no trade is recorded within 20 minutes of market open, the collector marks that day as a holiday and sleeps until the next session (`MARKET_SESSION_GUARD_MINUTES`).
- **New year:** at the start of each solar year, add that year's lunar holidays from the official calendar to `LUNAR_HOLIDAYS`. Until then, the session guard detects holiday days from market behavior, and the collector logs a warning.

## Multiple Instances

Compose runs two collectors (`COLLECTOR_REPLICAS`), and only one is the leader ([ADR 0010](adr/0010-high-availability.md)). Find the leader instance from the log (`leadership acquired`) or from the "Data Collection" dashboard. To test leader failover:

```bash
docker compose stop collector && docker compose up -d collector   # or kill one instance
docker compose logs collector | grep leadership
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| All cycles `failed` with `ConnectError` or `403` | VPN is on or the IP is blocked | Turn off the VPN or use split tunneling |
| `migrate` exits with an authentication error | The `.env` password doesn't match the previous ClickHouse volume | Restore the previous password, or `docker compose down -v` (:warning: this wipes data) |
| `collector failing` in the log and `stale` in `/health` | TSETMC is unreachable (usually VPN) | Turn off the VPN. The loop keeps going on its own; no restart is needed |
| The panel shows a "database unavailable" (503) message | ClickHouse is down or still starting up | `docker compose ps clickhouse` and `docker compose logs clickhouse` |
| `waiting for the first trade of the day` in the log during market hours | TSETMC still isn't showing today's trades | Normal; it waits up to 20 minutes and then marks the day as a holiday |
| All collectors are `standby` | The leadership lease in Redis is stuck (shouldn't happen: it has a TTL) | It releases itself after at most 60 seconds; `docker compose logs redis` |
| ClickHouse won't start: `Access to file denied: …/config.d/prometheus.xml` and `dependency failed to start: … is unhealthy` | An old image that mounted the config file from disk; a file that's owner-readable-only on the host (`0600`) isn't readable by the ClickHouse user inside the container (uid 101) | `docker compose --profile monitoring up -d --build`. From this version on, configs are copied into the image with fixed permissions ([ADR 0009](adr/0009-observability.md#config-baked-into-image-not-mounted)) |
| The collector started late and the fund's chart is missing the morning section | Backfill runs after the **third** cycle; or that fund was rejected because its trading times don't align with the live ticks | `intraday backfill done` in the log (lists `rejected_symbols`), or `SELECT status, count() FROM intraday_backfill_log FINAL WHERE day = today() GROUP BY status` ([ADR 0012](adr/0012-intraday-backfill.md)) |
| The collector keeps logging "market closed" | Outside market hours | Normal; for testing use `COLLECT_IGNORE_MARKET_HOURS=true` |
| The build hangs on `uv sync` | PyPI access | Turn the VPN on, or point `UV_INDEX_URL` at a mirror |

## Testing

| Command | What it does | Requires |
|---|---|---|
| `make test` | Unit tests | None (no network or database) |
| `make test-all` | Plus integration tests against real ClickHouse | `docker compose up -d clickhouse` |
| `make fixtures` | Records real API responses into `tests/fixtures/captured` and builds a small sample in `tests/fixtures/sample` | :warning: VPN off |
| `make probe` | Measures the watcher's delta-fetch performance | :warning: VPN off, during market hours |
| `make docs` | Builds the docs site with `--strict` | — |
| `make check` | All CI checks except the smoke test: lint, types, tests with coverage, panel, docs | ClickHouse running |
| `make web-test` | Panel type-checking and tests | `make web-install` |
| `uv run python scripts/loadtest.py` | Load test of the API read path ([results](09-quality-engineering.md#load-test)) | API running |
