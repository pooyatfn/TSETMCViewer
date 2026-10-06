---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# TSETMCViewer

Live ingestion, cleaning, storage, and analysis of **exchange-traded equity funds** on the Tehran Stock Exchange and Iran Fara Bourse. The goal is to build a clear, big-picture view of this market for traders and portfolio managers.

<div class="hero-tags">
<span>Every 60 seconds</span><span>ClickHouse</span><span>FastAPI</span><span>React + ECharts</span><span>Docker</span><span>Python 3.12 · asyncio</span>
</div>

[Start with the architecture](01-architecture.md){ .md-button .md-button--primary }
[Run the service](08-runbook.md){ .md-button }

</div>

## What does this service do?

<div class="grid cards two" markdown>

-   :material-clock-fast:{ .lg .middle } __Minute-by-minute ingestion__

    ---

    During market hours, price, volume, order book, retail/institutional trades, and NAV for every equity fund are fetched from TSETMC every minute.

-   :material-shield-check-outline:{ .lg .middle } __Quality control__

    ---

    After every fetch, data completeness and correctness are checked. Every issue is either corrected or flagged — no correction happens silently.

-   :material-database-cog-outline:{ .lg .middle } __Enrichment__

    ---

    Raw data is turned into metrics such as premium/discount, retail money flow, returns, and turnover.

-   :material-chart-box-outline:{ .lg .middle } __The big picture__

    ---

    The dashboard's charts are built to show, in a few seconds, where money is flowing, which funds are overpriced, and what the overall state of the fund market is.

</div>

<figure class="shot">
<img src="assets/screens/overview-light.webp#only-light" alt="Dashboard">
<img src="assets/screens/overview-dark.webp#only-dark" alt="Dashboard in dark theme">
<figcaption>The dashboard on real end-of-session data from 1 Mehr 1405. Each chart is explained in <a href="06-dashboard.md">Dashboard and Charts</a>.</figcaption>
</figure>

<div class="kpis">
  <div class="kpi"><b>159</b><span>equity, sector, index, and leveraged funds tracked</span></div>
  <div class="kpi"><b>10</b><span>quality checks and 13 flags per minute-level row</span></div>
  <div class="kpi"><b>2.9 ms</b><span>API response time with cache (349 requests/second)</span></div>
  <div class="kpi"><b>236</b><span>automated tests, 89% coverage, CI with Docker smoke test</span></div>
</div>

## Project requirements and where each is addressed

| # | Requirement | Where implemented | Where explained |
|:-:|---|---|---|
| 1 | Live ingestion every minute for all equity funds | `collector/service.py`, `pipeline/universe.py` | [Architecture](01-architecture.md), [ADR 0004](adr/0004-scheduling.md), [ADR 0007](adr/0007-fund-identity.md) |
| 2 | Storage after every fetch | `storage/`, migrations `0001`–`0004` | [Data Model](03-data-model.md), [ADR 0001](adr/0001-clickhouse.md), [ADR 0003](adr/0003-raw-first-ingestion.md) |
| 3 | Completeness and correctness checks, and preprocessing | `pipeline/validate.py`, `domain/quality.py` | [Data Quality](04-data-quality.md) |
| 4 | Identifying provider-supplied data, building supplementary base data, and the stage each is added at | `pipeline/transform.py`, `pipeline/history.py`, `domain/metrics.py` | [Data Sources](02-data-sources.md), [Financial Logic](05-financial-logic.md) |
| 5 | User dashboard for fetched and processed data | `web/` (fund table, per-fund page, quality card) | [Dashboard and Charts](06-dashboard.md) |
| 6 | Analytical charts for the big picture | `web/src/charts/options.ts` | [Dashboard and Charts](06-dashboard.md) |
| — | Docker and running in any environment | `docker-compose.yml`, `docker/` | [Runbook and Operations](08-runbook.md) |
| — | Code quality and repo structure | `tests/`, `.github/workflows/ci.yml` | [Testing and Hardening](09-quality-engineering.md) |
| — | Monitoring, alerting, and availability | `telemetry.py`, `monitoring/`, `collector/leadership.py` | [Monitoring and Alerting](11-monitoring.md), [ADR 0009](adr/0009-observability.md), [ADR 0010](adr/0010-high-availability.md) |

## Where should I start?

<div class="grid cards two" markdown>

-   :material-account-tie-outline: __Technical reviewer__

    ---

    [Architecture](01-architecture.md) ← [Technical Decisions](adr/index.md) ← [Testing and Hardening](09-quality-engineering.md) ← [Limitations](10-limitations.md). The "Day N review" sections in the ADRs show where a decision changed based on real data.

-   :material-chart-line: __Trader and portfolio manager__

    ---

    [Dashboard and Charts](06-dashboard.md) (the minute-by-minute routine for reading the dashboard) ← [Financial Logic](05-financial-logic.md) (the definition of every number and the finding on leveraged funds) ← [Data Quality](04-data-quality.md).

-   :material-code-braces: __Developer__

    ---

    [Runbook and Operations](08-runbook.md) ← [Data Model](03-data-model.md) ← [API](07-api.md) ← [Data Sources](02-data-sources.md).

-   :material-server-outline: __Service operator__

    ---

    [Runbook and Operations](08-runbook.md): VPN and networking, startup outside market hours, holidays, and troubleshooting ← [Monitoring and Alerting](11-monitoring.md): dashboards, alerting to "Bale", and a runbook for resolving each alert.

</div>

## Architecture at a glance

<figure class="diagram">
<img src="assets/diagrams/architecture.svg" alt="Overall service architecture">
<figcaption>Data flow from left to right: source → ingestion and processing → storage → API and cache → dashboard. The "new tick" event (orange line) invalidates the cache and pushes fresh data to the dashboard.</figcaption>
</figure>

## Documentation map

<div class="grid cards two" markdown>

-   :material-sitemap-outline: __[Architecture](01-architecture.md)__

    System components, design principles, and the flow of a single ingestion cycle.

-   :material-database-arrow-down-outline: __[Data Sources](02-data-sources.md)__

    What the provider supplies, what we build ourselves, and at which stage — with real-world measurements of the endpoints.

-   :material-table-large: __[Data Model](03-data-model.md)__

    Tables, keys, ClickHouse engines, and quality flags.

-   :material-shield-check-outline: __[Data Quality](04-data-quality.md)__

    Ten checks per cycle, how each is corrected, and why it was chosen that way.

-   :material-finance: __[Financial Logic](05-financial-logic.md)__

    Premium/discount, net asset value, retail money flow, returns — plus the finding on leveraged-fund NAV.

-   :material-chart-areaspline: __[Dashboard and Charts](06-dashboard.md)__

    Which question each chart answers for the trader and portfolio manager, and why that shape and that color.

-   :material-api: __[API](07-api.md)__

    Endpoints, the response contract, cache headers, and live events.

-   :material-scale-balance: __[Technical Decisions (ADR)](adr/index.md)__

    Every major choice, with context, rejected alternatives, and consequences.

-   :material-console: __[Runbook and Operations](08-runbook.md)__

    Running with Docker, networking notes (VPN), monitoring, and troubleshooting.

-   :material-shield-bug-outline: __[Testing and Hardening](09-quality-engineering.md)__

    Test strategy, CI with a smoke test, failure-mode behavior, and cache load testing.

-   :material-chart-bell-curve: __[Monitoring and Alerting](11-monitoring.md)__

    Prometheus, four Grafana dashboards, 16 alerts with unit tests, and alert delivery to "Bale"; a runbook for resolving each alert.

-   :material-map-marker-path: __[Limitations and Next Steps](10-limitations.md)__

    What the service doesn't know or doesn't do, and the suggested order for completing it.

</div>

## Progress Status

| Day | Scope | Status |
|:---:|---|:---:|
| 1 | Repo skeleton, Docker, ClickHouse schema, API clients, raw ingestion | <span class="pill done">Done</span> |
| 2 | Response parsing, fund list, full minute cycle, replay | <span class="pill done">Done</span> |
| 3 | Validation and preprocessing, quality report | <span class="pill done">Done</span> |
| 4 | Financial logic, history, API, Redis cache, and SSE | <span class="pill done">Done</span> |
| 5 | Dashboard and analytical charts, nginx container | <span class="pill done">Done</span> |
| 6 | Testing, CI, hardening, load testing | <span class="pill done">Done</span> |
| 7 | Left-to-right time axis, collector status in the dashboard, limitations, completing the docs | <span class="pill done">Done</span> |
| + | Holiday calendar, weighted premium and premium time series, Grafana monitoring and alerting, collector leadership and multiple API workers | <span class="pill done">Done</span> |
