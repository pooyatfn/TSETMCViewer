# ADR 0001 — ClickHouse as the Database

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 1</span></div>

!!! abstract "Summary"
    Data is append-only and never edited, and queries are analytical (few columns, many rows). A columnar database with compression, TTL, and materialized views was built for this pattern. The cost of this choice is the lack of transactions and asynchronous deduplication, offset by idempotent design.

## Context

- Write volume: about 120 funds × 210 minutes per day ≈ 25 thousand clean rows per day, plus raw responses (a few megabytes of JSON per minute). This volume is low, but **it only grows and is never updated**.
- The read pattern is analytical: "total real-money inflow across all funds by day", "the premium/discount distribution at this instant", "the 30-day return of all funds". These queries run over few columns and many rows.
- The dashboard must be fast, without a separate caching layer.

## Decision

**ClickHouse 24.8 (LTS)** with these engines:

| Table | Engine | Reason |
|---|---|---|
| `raw_snapshots` | `MergeTree` + `ZSTD(6)` compression + `TTL 30 DAY` | Append-only. The JSON responses are repetitive and compress more than 10x. Automatically purged after 30 days. |
| `fund_ticks` | `ReplacingMergeTree(ingested_at)` on `(ins_code, ts)` | A duplicate write for the same minute (retry or re-run) doesn't create duplicates; the latest version is kept. |
| `funds`, `fund_daily` | `ReplacingMergeTree(updated_at)` | Reference data that changes slowly; the latest version is always read. |
| Aggregates (Day 4) | `AggregatingMergeTree` + Materialized View | Daily and intraday aggregates are computed on insert, not on read. |

Partitioning is monthly (`toYYYYMM`), so that for raw data a full partition can be dropped once the TTL expires.

## Rejected Options

| Option | Why not |
|---|---|
| **PostgreSQL + TimescaleDB** | Would have been entirely sufficient and has real `UPDATE`/`UNIQUE`. But columnar analytical queries are far faster in ClickHouse, raw-data compression is better, and incremental materialized views exist by default. For a product whose core is "analysis", ClickHouse is the more natural choice. |
| **Plain PostgreSQL** | As data grows, aggregate queries get slow and we'd need a cache. |
| **InfluxDB / QuestDB** | Good for time series, but weaker at reference data and joins, and lack full SQL. |
| **MongoDB** | Easy to store raw JSON, but weak at columnar analytics and schema validation. |

## Consequences

- ➕ Dashboard queries over months of data run in milliseconds; excellent compression; built-in TTL and MV.
- ➖ **Deduplication is asynchronous.** `ReplacingMergeTree` removes duplicates during merge, not on insert. Queries that need full accuracy use `FINAL` or `argMax`. This rule is centralized in the API's read layer.
- ➖ **No transactions.** Writing one cycle's data is not atomic. Mitigation: a `run_id` on every row and idempotent inserts. An incomplete cycle can be re-run with the same `tick`.
- ➖ **UPDATE/DELETE is expensive** (mutation). The design is deliberately "append-only", and corrections are made by inserting a new version, not by editing.
- ➖ ClickHouse isn't suited to many small inserts. The collector inserts each cycle's data **in a single batch**, i.e. about one insert per minute per table.
