# Architecture

<p class="lead">What the system is built from, how data flows through it, and the design principles that shaped this structure.</p>

<figure class="diagram">
<img src="assets/diagrams/architecture.svg" alt="Overall service architecture">
<figcaption>Figure 1 — Service overview. Data flows left to right.</figcaption>
</figure>

## Components

| Service | Responsibility | Lifecycle |
|---|---|---|
| `clickhouse` | Stores raw, clean, reference and aggregated data | Long-running |
| `migrate` | Creates the database and applies migrations | Runs once; everything else waits for it to finish successfully |
| `collector` | Fetches, stores raw, parses, validates, writes, announces ticks | Long-running; sleeps outside market hours |
| `api` | Reads and serves data, caches responses, pushes to the panel | Long-running |
| `redis` | Response cache and tick event channel | Long-running |
| `web` | User panel on port 8080: static React files behind nginx, and an `/api` proxy to the API; the "Docs" tab lives here too | Long-running |

!!! tip "One image, several commands"
    The three Python services (`migrate`, `collector` and `api`) are built from **a single image** and differ only in their command (`tsetmc-viewer migrate | collect | api`). The result: one build, one version of the code, and no drift between services.

## Design Principles

<div class="grid cards two" markdown>

-   :material-file-document-outline: __Separate transport from interpretation__

    Clients return only bytes and metadata (`RawResponse`); parsing is a separate step. The raw response is always stored first, before any assumption about its structure. ([ADR 0003](adr/0003-raw-first-ingestion.md))

-   :material-identifier: __One id per cycle__

    Every collector run has a `run_id`. Raw responses, clean rows and quality findings all tie back to it, so "where did the 10:41 data come from?" is answered with a single query.

-   :material-repeat-once: __Idempotency__

    The `fund_ticks` table keys on `(ins_code, ts)`. Repeating a cycle never produces duplicate data, and migrations can be run any number of times.

-   :material-shield-half-full: __Partial failure, not total failure__

    If one endpoint errors out, the rest are still stored and the cycle is recorded with status `partial`. Programming errors are deliberately not swallowed, so they stay visible.

-   :material-clock-outline: __Timezone-aware time__

    All timestamps, in both Python and ClickHouse, are in `Asia/Tehran`. Iran has not observed daylight saving since 1401, and `zoneinfo` models this correctly.

-   :material-cog-outline: __Configuration from environment only__

    All settings are read from environment variables with `pydantic-settings` and validated at startup (12-factor).

</div>

## Data Layers

<figure class="diagram">
<img src="assets/diagrams/data-layers.svg" alt="Data layers">
<figcaption>Figure 2 — Data moves from "raw" to "clean" and then to "analytical". The API never reads raw data.</figcaption>
</figure>

## Code Layers

| Module | Responsibility | I/O type |
|---|---|---|
| `config.py` | Typed settings from environment variables | — |
| `clock.py` | "Is the market open right now?" and alignment to the minute boundary | — |
| `sources/` | HTTP clients: `http.py` (retry, backoff, semaphore), `tsetmc.py` | Network |
| `collector/` | Orchestrates a single cycle and the long-running loop | — |
| `storage/` | ClickHouse connection, migrations, repository | Database |
| `api/` | Presentation layer: `app.py`, `deps.py`, `routes/` | HTTP |

Dependencies point in one direction only: `api` and `collector` depend on `storage` and `sources`, never the reverse. `collector` depends on a `Protocol` (`RunSink`), not a concrete class, so it can be tested without a database using an in-memory implementation.

## A Collection Cycle

<figure class="diagram">
<img src="assets/diagrams/cycle.svg" alt="Time budget of a one-minute cycle">
<figcaption>Figure 3 — Time budget of a cycle based on real measurement. With gzip compression, scanning the whole market takes about 1 second, and most of the time goes to NAV requests (<a href="adr/0006-caching.md">ADR 0006, Day 4 revision</a>).</figcaption>
</figure>

1. `tick` = the current time rounded to the minute. All funds get a shared timestamp.
2. Parallel fetch of aggregate endpoints (market watch, individual/institutional) and each fund's NAV, under a concurrency cap.
3. Store raw responses in `raw_snapshots`.
4. Parse → filter to the list of equity funds → validate → repair or flag.
5. Batch write to `fund_ticks` and `data_quality_log`.
6. Record `collection_runs` and publish a "tick N" event.

??? info "Implementation status"
    - [x] Raw storage and cycle logging — Day 1
    - [x] Daily fund list, per-fund NAV, parsing, tick assembly, `market_ticks` — Day 2
    - [x] `replay`: rebuild a day's ticks from raw data — Day 2
    - [x] Validation and repair, quality reporting — Day 3
    - [x] Daily history, financial logic, API, tick publishing, Redis cache and SSE — Day 4
