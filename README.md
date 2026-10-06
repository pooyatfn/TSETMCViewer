# TSETMCViewer

A service for live ingestion, cleaning, storage, and analysis of **tradable equity investment fund** data on the Tehran Stock Exchange.

- Data for every equity fund is pulled from TSETMC once a minute during market hours.
- The raw response is stored before any processing; then validation, preprocessing, and storage in ClickHouse.
- Base fund metadata (type, unit count, net asset value) is completed daily from TSETMC's symbol data.
- A web dashboard (React + ECharts) shows the overall picture of the fund market.

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/overview-light.webp" alt="Dashboard overview"/><br/><sub>Overview: KPI tiles and market map, on real end-of-session data</sub></td>
<td width="50%"><img src="docs/assets/screens/treemap.webp" alt="Fund market map"/><br/><sub>Market map: cell area = net assets, color = today's price change</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/screens/money-map.webp" alt="Money map and valuation"/><br/><sub>Money map: does retail money follow expensive funds or cheap ones</sub></td>
<td width="50%"><img src="docs/assets/screens/docs-tab.webp" alt="Documentation tab inside the panel"/><br/><sub>The full service documentation, inside the panel itself — no separate service</sub></td>
</tr>
</table>

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
curl localhost:8000/health
docker compose logs -f collector   # outside market hours: history + last session's closing snapshot (VPN off)
curl localhost:8000/api/v1/overview
open http://localhost:8080                             # web dashboard
docker compose --profile monitoring up -d              # Grafana on :3000, alerts to Bale (optional)
docker compose --profile ha-storage up -d               # two ClickHouse replicas + Keeper (optional, in addition to the above)
```

| Service | Role |
|---|---|
| `clickhouse` | time-series database |
| `migrate` | creates the database and applies migrations (runs once and exits) |
| `collector` | the minute-aligned ingestion loop during market hours (holiday-aware); two instances with one leader |
| `redis` | caches responses and carries the "new tick" event channel (optional; the service still works without it) |
| `api` | FastAPI on port 8000 — interactive docs at `/docs` |
| `web` | the web dashboard on port 8080 (nginx: built React files + `/api` proxy); the "Documentation" tab lives here |
| `prometheus` · `alertmanager` · `grafana` · `alert-relay` | monitoring and alerting (`monitoring` profile); [guide](docs/11-monitoring.md) |
| `clickhouse-0` · `clickhouse-1` · `clickhouse-keeper` | two `ReplicatedMergeTree` replicas coordinated via Keeper (`ha-storage` profile, optional and alongside `clickhouse` above, not a replacement for it); [ADR 0011](docs/adr/0011-clickhouse-replication.md) |

**Network note:** TSETMC generally blocks IPs outside Iran. Pull images (Docker Hub) with a VPN on, and run the collector with the VPN off — details in the [runbook](docs/08-runbook.md).

## What's where

| Question | Answer |
|---|---|
| What is each chart for? | [Dashboard and Charts](docs/06-dashboard.md) |
| How exactly are premium, net assets, and money flow computed? | [Financial Logic](docs/05-financial-logic.md) |
| How is TSETMC's data checked and fixed? | [Data Quality](docs/04-data-quality.md) |
| Why ClickHouse, why raw data first, why this cache? | [Architecture Decisions (ADR)](docs/adr/index.md) |
| What's tested, and how does the service behave under failure? | [Testing and Hardening](docs/09-quality-engineering.md) |
| How do I find out about an outage quickly? | [Monitoring and Alerting](docs/11-monitoring.md) |
| What's still missing? | [Limitations and Next Steps](docs/10-limitations.md) |

## Development

```bash
make install     # uv sync + pre-commit
make test        # unit tests (no database needed)
make test-all    # all tests, with ClickHouse running
make lint typecheck
make fixtures    # record real API responses for tests (VPN off)
make web-install web-dev   # dashboard on :5173, proxied to the local API
make web-test    # dashboard typecheck and tests
make check       # every CI check except the Docker smoke test
make loadtest    # API load test (against :8000)
```

## Repository layout

```
src/tsetmc_viewer/
  config.py            settings (pydantic-settings, from env)
  clock.py             calendar and market hours (Asia/Tehran)
  sources/             HTTP client and TSETMC response models
  collector/           ingestion loop, leadership across instances, heartbeat
  alerting/            alert relay: Alertmanager ← Bale / Telegram / webhook
  telemetry.py         all Prometheus metrics in one place
  storage/             ClickHouse connection, migrations, write repository
  domain/              pure financial logic: fund identity, premium, money flow, Jalali calendar
  pipeline/             transform, validation/preprocessing, raw-data replay, history
  analytics/           dashboard analytical queries
  api/                 FastAPI: app, dependencies, cache, SSE, routes
web/src/
  api/                 API client and contract types
  charts/              ECharts wrapper, color tokens, each chart's option builder
  components/ views/   cards, table, dashboard, and the fund page
tests/                 unit + integration tests (real ClickHouse)
scripts/               side tools (fixture recording, load test)
docker/                Dockerfiles (service, panel + nginx) and ClickHouse config
monitoring/            Prometheus (rules + tests), Alertmanager, Grafana (dashboards as code)
docs/                  documentation (MkDocs Material) and ADRs
```
