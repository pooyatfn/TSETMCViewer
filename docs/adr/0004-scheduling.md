# ADR 0004 — Wall-Clock-Aligned Minute Scheduling

<div class="adr-meta"><span>Status: Accepted</span><span>Date: Day 1</span></div>

!!! abstract "Summary"
    A per-minute job with one condition (market is open) doesn't need scheduling infrastructure. A 30-line loop aligned to the wall-clock minute boundary doesn't drift, and keeps the timestamp of all funds in sync.

## Context

A periodic job (every 60 seconds) only during market hours (Saturday through Wednesday, 9:00 to 12:30 Tehran time) and a daily job (sync the fund list before market open).

## Decision

A simple `asyncio` loop in `Collector.run_forever`:

1. If the market is closed, sleep until the next open (at most one hour at a time).
2. Run one cycle. Any exception is logged and the loop continues.
3. Sleep until the **next wall-clock minute boundary** (`seconds_until_next_tick`), not "60 seconds after it finished."

**Why align to the wall clock?** If each cycle started 60 seconds after the previous one finished, each cycle's execution time would accumulate and timestamps would gradually drift. With alignment, all data lands on whole minutes (…:01:00, …:02:00). This makes JOINs between funds and chart rendering simple, and any missed minute is recognizable as a distinct "hole."

## Rejected Options

- **APScheduler:** has capabilities like job stores and misfire policies that aren't needed for a single job, and the "market hours only" logic still has to be written separately anyway.
- **cron in the container:** each run is a new process with startup overhead, and connections aren't kept between runs.
- **Celery beat + worker + broker:** three extra components for a once-a-minute job.

## Consequences

- The collector has a single instance (replica). Running multiple instances causes duplicate inserts. Thanks to `ReplacingMergeTree` the data isn't corrupted, but the load on TSETMC doubles. For future HA: a leader lock.
- Official holidays aren't in the calendar yet. On a holiday, cycles get unchanged responses, and the "stale data" check (doc 04) flags it. The holiday list is added in Next Steps.

## Day 5 Review: Startup Outside Market Hours {#day-5-review-startup-outside-market-hours}

**Problem.** The system's first real run was on a trading day's evening. The collector slept until the next business-day morning and the panel had no data at all, even though TSETMC still showed all of the previous session's closing figures. For a user bringing the system up after 12:30 or on a weekend — which is most of the time — this is a bad experience.

**Decision.** `Collector.bootstrap()` runs before the main loop (unless `COLLECT_BOOTSTRAP=false`):

<div class="grid cards two" markdown>

-   :material-calendar-search: __1. Which session?__

    ---

    The session date TSETMC is showing is read from `marketActivityDEven` in the market overview (a small request). Our own calendar doesn't know this: Thursday, Friday, or an official holiday all push the last session earlier or later.

-   :material-history: __2. History up to that session__

    ---

    If the table is empty, the whole window (400 days) is loaded. Otherwise, only the gap between the last stored day and the session, with a minimum of 10 days (the number of requests is the same either way, since each endpoint returns the whole history in a single response).

-   :material-camera-timer: __3. Closing snapshot of the session__

    ---

    If there is **no** minute-level data at all for that session, a normal cycle runs (same pipeline, same validation, same raw storage), but with timestamp **the closing time of that same session**, not "now." A `closing snapshot` note is recorded in `collection_runs`.

-   :material-shield-alert-outline: __4. Guards__

    ---

    Nothing runs during market hours (the live loop is responsible for that). If the feed shows no trades at all (pre-open reset the next morning), no snapshot is taken. A network error is only a warning and the service still comes up.

</div>

The same logic also runs after every market close. So if the collector was off during a session, that day at least has its closing state, and the history is always up to date through the last session.

**Why timestamp it with the closing time?** `session_date` in the API is "the last day that has data." If the snapshot were stored with the current time (say, a Friday), the panel would show Friday as a trading session and returns and flows would be shifted by a day.

**What this doesn't build.** The intraday curve for a session during which the collector was off cannot be reconstructed (ADR 0003). In that case the panel says so explicitly, instead of showing an empty chart.

**Tests:** `tests/test_bootstrap.py`: a fresh install on a holiday (400-day history, snapshot timestamped 12:30 of the previous session, and idempotent on a repeat startup), market hours (no request is sent), pre-open reset, requesting only the history gap, and an integration test showing the API serves the previous session after bootstrap.

## Post-Day-7 Review: Holiday Calendar and Multiple Instances {#post-day-7-review-holiday-calendar-and-multiple-instances}

Both limitations noted under "Consequences" were addressed:

- **Official holidays.** `domain/calendar.py` has three layers: official holidays (solar holidays by fixed rule, and 1405 lunar holidays from the published official calendar), operator-declared closures (`MARKET_EXTRA_HOLIDAYS`), and **what the market actually did**. Before each day's first cycle, the collector reads, with a small request, the session date TSETMC is showing. If no trade is recorded within 20 minutes of market open, that day is recorded in the `market_calendar` table as an undeclared holiday. If a day listed as a holiday has trades, the mistaken entry is corrected and collection resumes. Both cases are tested (`tests/test_calendar.py`). For years without a lunar table, this same session guard learns holidays from market behavior.
- **A single instance.** Multiple collectors now run with leadership via Redis ([ADR 0010](0010-high-availability.md)).

## Review: The Market-Close Edge

The first real day (4 Mehr 1405) surfaced two bugs. The last cycle of a session is at 12:29 (the 12:30 cycle starts when the market is no longer open), so each day's last data point stays at 12:29. And since no tick was published after that, open panels stayed "live" until the next day.

- **Closing cycle.** The loop's first wake-up after close, if today had a live cycle, records and publishes a cycle timestamped **12:30** (`session close`). Publishing that tick updates panels and turns "live" into "market closed."
- **Post-close refresh.** 30 minutes later, the closing snapshot is now **always** taken (not only when the day has no minute-level data) and replaces that 12:30 timestamp with the official closing figures; `ReplacingMergeTree` keeps the newer row.
- **Correct even without the collector.** Whether the market is open or closed became part of the cache key ([ADR 0006](0006-caching.md#post-day-7-review-the-cache-version-isnt-just-the-tick)) and the panel re-queries the overview every minute, so even if no tick arrives at the moment of closing, "live" still turns off.
