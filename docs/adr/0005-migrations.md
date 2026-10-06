# ADR 0005 — Numbered SQL File Migrations

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 1</span></div>

!!! abstract "Summary"
    ClickHouse has no DDL transactions, and Alembic was not built for it. Numbered SQL files, idempotent and locked with a checksum, are the simplest reliable approach.

## Context

The schema must be versioned and built with a single command in any environment. ClickHouse has neither transactional DDL nor a mature SQLAlchemy driver.

## Decision

- Files `src/tsetmc_viewer/storage/migrations/NNNN_name.sql`, built into the package and shipped in the image.
- A ~60-line runner (`storage/migrate.py`):
  - A `schema_migrations` table tracks the version, name, and **checksum** of each applied file.
  - Changing a file that was already applied is an error. Schema changes only happen through a new file.
  - Every statement must be idempotent (`IF NOT EXISTS`). A test checks this rule for all files, since ClickHouse cannot roll back a half-applied file.
- In compose, the `migrate` service runs once, and the other services wait on it with `service_completed_successfully`.

## Rejected Options

- **Alembic:** depends on SQLAlchemy and transactional DDL. Fragile with ClickHouse.
- **External tools (golang-migrate, goose):** support ClickHouse, but add another binary and image.
- **Creating tables in code at application startup:** no versioning or history.

## Consequences

Migrations are forward-only. Rollback happens via a new migration. A column change in ClickHouse (`ALTER`) is an asynchronous mutation and is documented in the migration file.

## Day 5 Review: Migration 0004 Failed on ClickHouse 24.8.14

**What happened.** On the first full run on the developer's system, the `migrate` service stopped at file 0004 with this error:

```text
Code: 70. Conversion from AggregateFunction(argMax, UInt64, Tuple(DateTime, DateTime64(3)))
to AggregateFunction(argMax, UInt64, Tuple(ts DateTime, ingested_at DateTime64(3))) is not supported
```

**Cause.** The `fund_eod` columns have a **named** tuple `Tuple(ts …, ingested_at …)`, and the materialized view was building the value with a plain tuple `(ts, ingested_at)`. Whether ClickHouse names this tuple or not depends on the `enable_named_columns_in_function_tuple` setting, and that setting's default **changed between two patch versions of the same branch**: it is on in 24.8.4 (our development environment) and off in 24.8.14 (the `24.8` image on the user's system). The `24.8` tag in compose is not pinned, so anyone could end up with a different patch.

**Fix.** The view now explicitly CASTs the tuple type, so it no longer depends on any setting:

```sql
WITH CAST((ts, ingested_at), 'Tuple(ts DateTime(''Asia/Tehran''), ingested_at DateTime64(3, ''Asia/Tehran''))') AS version
SELECT … argMaxState(close_price, version) AS close_price, …
```

A new integration test (`test_eod_view_works_whatever_the_tuple_naming_default`) runs the migrations with both setting values and checks that the view correctly keeps the day's latest value.

**Why file 0004 was edited, not a new file 0005.** This ADR's rule is that an applied file is not edited. But 0004 was **never** applied on 24.8.14: the error occurs before it is recorded in `schema_migrations`, and since all statements are `IF NOT EXISTS`, re-running continues from the same point. A file 0005 would not have helped, since a fresh install would never get past 0004. The only databases that have recorded the old 0004 are development databases on 24.8.4, and the checksum blocks running it there (the correct behavior). The fix for those is to rebuild the database.

**Lesson.** The database engine version is part of the schema contract. ClickHouse changes semantic defaults even between patches, so DDL must not rely on defaults. As of day 6, CI runs migrations against the **same image** that compose uses.

## Day 6 Review

Done. The ClickHouse service in CI uses the same tag as `docker-compose.yml`, and `tests/test_repo_consistency.py` fails if the two drift apart. The CI smoke test also brings up the whole stack with `docker compose` and checks that `migrate`'s exit code is zero ([Testing and Hardening](../09-quality-engineering.md#ci)).
