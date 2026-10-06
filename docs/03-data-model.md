# Data Model

<p class="lead">The tables, keys and ClickHouse engines, and the reasoning behind each choice. The schema only ever changes through migration files (<a href="../adr/0005-migrations.md">ADR 0005</a>), and this page is a readable version of those same files.</p>

<figure class="diagram">
<img src="assets/diagrams/data-model.svg" alt="Data model">
<figcaption>Figure 1 — Three table categories: reference (daily), time series (per-minute), and operations and audit. Each clean row's <code>run_id</code> ties it back to the cycle and the raw response that produced it.</figcaption>
</figure>

## Modeling Principles

<div class="grid cards two" markdown>

-   :material-sort-ascending: __Sort key = query pattern__

    ---

    In ClickHouse, `ORDER BY` acts as the primary index. Nearly every panel query is "one or more funds over a time range", so `fund_ticks`'s key is `(ins_code, ts)`.

-   :material-content-duplicate: __Uniqueness without locking__

    ---

    `ReplacingMergeTree(ingested_at)` keeps only the latest version per key. Re-running a cycle, or replaying a whole day, never creates duplicate rows.

-   :material-calendar-month: __Monthly partitioning__

    ---

    Roughly 150 funds × 210 minutes × 22 days ≈ 700K rows per month. Smaller partitions would only multiply the number of parts. Raw data is the exception: it partitions daily so an entire partition's TTL can be dropped at once.

-   :material-timer-sand: __Time is always timezone-aware__

    ---

    Every timestamp column is `DateTime('Asia/Tehran')`, so `toDate(ts)` gives the correct trading day, not the UTC day.

</div>

## Tables

=== "fund_ticks"

    **One row per fund per minute.** This is the heart of the system, and every analysis is built from it.

    | Group | Columns | Source |
    |---|---|---|
    | Key | `ins_code`, `ts` (rounded minute) | — |
    | Price | `last_price`, `close_price`, `open_price`, `high_price`, `low_price`, `prev_close` | Market watch |
    | Trading | `volume`, `value`, `trade_count` | Market watch |
    | Secondary board | `block_volume`, `block_value` | Sum of boards `…0002`/`…0004` ([ADR 0007](adr/0007-fund-identity.md)) |
    | NAV | `nav_redemption`, `nav_subscription`, `nav_at` | ETF |
    | Order book | `bid_price`, `bid_volume`, `ask_price`, `ask_volume` (level 1) | Market watch |
    | Individual/Institutional | Buy/sell volume, value and count for both groups | ClientTypeAll |
    | Quality | `quality_flags` (bitmask), `run_id`, `ingested_at` | [Validation](04-data-quality.md) |

    All prices and values are **Rials, integer** (`UInt64`). Floating-point error in summed trade values is not acceptable.

=== "funds / fund_daily"

    | Table | Key | Content | Updated |
    |---|---|---|---|
    | `funds` | `ins_code` | Symbol, name, ISIN, type, market, board, `is_active` | Daily, before market open |
    | `fund_daily` | `(ins_code, trade_date)` | Units outstanding, net asset value | Daily |

    A fund that is delisted is **not deleted**; it gets a new version with `is_active = 0` so its history stays intact for charts.

=== "market_ticks"

    Total index, equal-weight index, market value and market status for every minute. The benchmark for comparing fund returns against the overall market.

=== "Daily"

    | Table | Engine | Key | Content |
    |---|---|---|---|
    | `fund_history_daily` | `ReplacingMergeTree(updated_at)`, yearly partitioning | `(ins_code, trade_date)` | Daily prices and **official** individual/institutional values; initial 400-day backfill and updated 30 minutes after market close |
    | `fund_eod` | `AggregatingMergeTree` with MV `fund_eod_mv` | `(ins_code, trade_date)` | Each day's final state from live data: closing price, value, NAV, money inflow |

    `fund_eod` is built entirely from `argMax(…, (ts, ingested_at))`. The last value of the day is independent of how many times a row was repeated, so replay and forward-fill don't corrupt it. `sum` lacks this property, which is why it isn't used in the MV.

=== "Operational"

    | Table | Role | Retention |
    |---|---|---|
    | `raw_snapshots` | Raw response for every request | 30 days |
    | `collection_runs` | Status of each cycle: expected funds vs. received | Permanent |
    | `data_quality_log` | Every validation finding and corrective action | 180 days |
    | `schema_migrations` | Migration version and checksum | Permanent |

## Quality Flags

Every `fund_ticks` row has a `quality_flags` integer where each bit is a status. This keeps the table narrow and filtering cheap:

```sql
-- Only ticks that have a NAV
SELECT * FROM fund_ticks WHERE bitAnd(quality_flags, 2) = 0
```

| Bit | Value | Flag | Meaning | Since |
|:-:|--:|---|---|---|
| 1 | 2 | `NAV_MISSING` | NAV was not received | Day 2 |
| 2 | 4 | `NAV_STALE` | NAV calculation time is older than the threshold | Day 3 |
| 3 | 8 | `CLIENT_TYPE_MISSING` | Fund was absent from individual/institutional data | Day 2 |
| 4 | 16 | `FLOW_VALUE_ESTIMATED` | Individual/institutional Rial value is estimated (volume × average price) | Day 2 |
| 5 | 32 | `NO_TRADES` | No trades yet today | Day 2 |
| 6 | 64 | `PRICE_OUT_OF_RANGE` | Price outside the day's allowed range | Day 3 |
| 7 | 128 | `CUMULATIVE_DECREASE` | Cumulative volume or value decreased | Day 3 |
| 8 | 256 | `FORWARD_FILLED` | Row was filled from the previous tick | Day 3 |
| 9 | 512 | `STALE_QUOTE` | The entire market-watch feed hasn't changed for several cycles | Day 3 |
| 10 | 1024 | `CLIENT_VOLUME_MISMATCH` | Individual + institutional sum doesn't match total volume | Day 3 |
| 11 | 2048 | `NAV_CARRIED` | NAV carried over from the previous tick | Day 3 |
| 12 | 4096 | `NAV_JUMP` | NAV changed by more than the threshold | Day 3 |
| 13 | 8192 | `RANGE_REPAIRED` | High/low was recomputed | Day 3 |

!!! warning "Storage contract"
    Bit numbers are part of the stored data format. New bits are only appended; no bit ever changes its number (`domain/quality.py`).

## Migration History

| File | Change | Reason |
|---|---|---|
| `0001_init.sql` | Base tables | Day 1 |
| `0002_pipeline_columns.sql` | `nav_at`, institutional value and count, `block_*`, `funds.market/board`, `market_ticks` table | Result of mapping real TSETMC responses |
| `0003_quality_counters.sql` | `collection_runs.issues/filled/repaired` | Cycle-level quality monitoring |
| `0004_history_and_eod.sql` | `fund_history_daily`, `fund_eod` and `fund_eod_mv` | Periodic returns, official money inflow, end-of-day NAV |

All `0002` statements use `ADD COLUMN IF NOT EXISTS`, so re-running it on a database left in a half-applied state is safe.
