# Architecture Decision Records (ADR)

<p class="lead">Every significant architecture decision is recorded in a short document: context, decision, rejected options, and consequences. These documents aren't rewritten over time. If a decision changes, a new ADR replaces the old one.</p>

<div class="grid cards two" markdown>

-   :material-database: __[0001 · ClickHouse](0001-clickhouse.md)__

    Why a columnar database and not PostgreSQL/TimescaleDB; `MergeTree` engines and the cost of not having transactions.

-   :material-language-python: __[0002 · Python async](0002-python-async-stack.md)__

    asyncio, httpx, and FastAPI for work that's almost entirely I/O-bound.

-   :material-archive-outline: __[0003 · Raw data first](0003-raw-first-ingestion.md)__

    The source response is stored before parsing, because intraday data can't be recovered.

-   :material-timer-outline: __[0004 · Minute-aligned scheduling](0004-scheduling.md)__

    A wall-clock-aligned loop instead of APScheduler or Celery.

-   :material-source-branch: __[0005 · Migrations](0005-migrations.md)__

    Numbered SQL files with checksums instead of Alembic.

-   :material-lightning-bolt-outline: __[0006 · Caching](0006-caching.md)__

    Six cache layers and invalidation tied to the tick event.

-   :material-card-account-details-outline: __[0007 · Fund identity](0007-fund-identity.md)__

    Primary board, secondary boards, and options: which symbol counts as a "fund"?

-   :material-monitor-dashboard: __[0008 · Web panel](0008-web-panel.md)__

    React + Vite + ECharts with no router or state manager; nginx same-origin with the API.

-   :material-chart-bell-curve: __[0009 · Observability](0009-observability.md)__

    Prometheus, Grafana, and Alertmanager; a Persian relay for Bale and Telegram; unit-tested alert rules.

-   :material-server-network: __[0010 · High availability](0010-high-availability.md)__

    Collector leadership via a Redis lease; multiple API workers with distributed single-flight.

-   :material-database-sync-outline: __[0011 · ClickHouse replication](0011-clickhouse-replication.md)__

    Two `ReplicatedMergeTree` replicas with one Keeper, optional; and why it still isn't real HA.

-   :material-history: __[0012 · Backfilling missed intraday minutes](0012-intraday-backfill.md)__

    Today's tick-level trades, validated against live ticks, in a separate table; price and volume only.

-   :material-calendar-clock: __[0013 · Backfilling past sessions](0013-session-backfill.md)__

    Price history (not tick-level trades) for the past 5 days, validated against the official closing figure.

</div>

## Template

```text
# ADR NNNN — Title
Status · Date
Context           ← what problem, what constraints
Decision          ← what was chosen
Rejected Options   ← and why
Consequences       ← benefits (➕), costs (➖), and risks (⚠️)
```
