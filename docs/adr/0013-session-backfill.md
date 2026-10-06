# ADR 0013 — Backfilling Past Sessions from Price History

<div class="adr-meta"><span>Status: Accepted</span><span>Date: After Day 7</span><span>Based on a real-world test on 5 Mehr 1405 against 29920920</span></div>

!!! abstract "Summary"
    At startup (outside market hours), the 5 most recent trading days during which the collector was never running at all are backfilled from `ClosingPrice/GetClosingPriceHistory`: price, volume, value, and trade count, minute by minute, from market open to close. Unlike [ADR 0012](0012-intraday-backfill.md) (which only knows about today), this endpoint provides any past day. Since there is no live tick to compare against, each day/fund is only stored when its final total agrees with the official end-of-day figure (`fund_history_daily`). Same table and same limitation as ADR 0012: no NAV and no real/legal-entity flow.

## Context

- The user asked: "Can you also collect minute-by-minute data for past days?" — in addition to the existing 400-day **daily** history ([History Backfill ADR](../02-data-sources.md)).
- ADR 0012 explicitly uses `Trade/GetTrade` only for "today"; its code even enforces this (`if day != today: return`).
- The other two endpoints, `GetTradeHistory` and `GetClosingPriceHistory`, had been tested in the same day's measurement with `{date}` = **today**, and returned 502/empty — a result recorded in ADR 0012 as "rejected". But their names ("History") suggested the same thing: maybe they only work with a **past, closed** day.
- This hypothesis was recorded in docs/02, and the user was asked to test it with VPN off and a real past date (since this sandbox environment has no access to TSETMC).
- The real result (5 Mehr 1405, tested date 29 Shahrivar, 15 sample funds):

| Endpoint | Result | Takeaway |
|---|---|---|
| `Trade/GetTradeHistory/{ins}/{date}/false` | 12 of 15 funds returned `rows: 0` despite having thousands of trades (Yaghut: 48,022 trades, zero rows) | **Unreliable**; no pattern was found between succeeding/failing funds either. Dropped |
| `ClosingPrice/GetClosingPriceHistory/{ins}/{date}` | 14 of 15 funds returned real rows (only Hira was empty); fast and cheap (extrapolated: 5.4 MB and ~7 seconds for 334 funds) | **Usable**. The row shape (`pDrCotVal`, `qTotTran5J`, `qTotCap`, `zTotTran`) is exactly the same `DailyPriceRow` model already parsed for the 400-day bootstrap — the same feed, with added time granularity (`hEven`) |

- Unlike `Trade/GetTrade`, each `GetClosingPriceHistory` row is itself a **running cumulative total** (not a single trade), so no summation is needed — just sort by time and sample at each minute boundary.

## Decision

```text
In bootstrap (outside market hours), after catch_up_history and closing_snapshot:
  For the 5 most recent trading days up to and including the last session (holidays skipped):
    For every fund with no decision recorded yet for that day (intraday_backfill_log):
      ClosingPriceHistory  →  raw response into raw_snapshots
      tape  = rows sorted by hEven (each row is already cumulative)
      check = the final total (volume, value) must agree with fund_history_daily for that same day (±1%)
      if it agrees   → minutes from market open to close go into fund_ticks_backfill
      otherwise       → rejected in intraday_backfill_log, nothing is stored
```

| Decision | Reason |
|---|---|
| Same tables (`fund_ticks_backfill`, `intraday_backfill_log`) | Same data limitation (no NAV/real-legal flow) and same philosophy (check before storing); no new migration needed |
| Checking against the **official end-of-day figure**, not live ticks | There is no live tick for a past day; the only trustworthy source is the same table bootstrap already fills |
| **One** check instead of checking every minute | The cumulative total is only comparable to the official figure in the last row; a mid-way point has no meaningful "right/wrong" |
| **5 days**, not 7 | The measured cost (~7 seconds/day for the whole market) is small, but each day is a separate request; 5 days meets the user's request with a margin of error without extra requests for days that, like Hira, always come back empty | 
| Only during **bootstrap** (startup, outside market hours) | This only needs to happen once a day, not every minute; there's no reason to compete with the live cycle for TSETMC bandwidth |
| Idempotent per (day, fund) | `backfilled_funds(day)` already existed for ADR 0012 and works here unchanged; an incomplete bootstrap resumes on the next startup |

## Rejected Options

| Option | Why not |
|---|---|
| `Trade/GetTradeHistory` instead of `GetClosingPriceHistory` | Returned empty for 80% of the sample despite having trades; no pattern to predict "which fund will work" |
| Backfilling all 400 days | Far more cost and risk for a scope the user didn't ask for; the daily (not minute-level) history already covers 400 days |
| Running this in the live cycle (like ADR 0012) | Only makes sense once, at startup; past days don't change, so there's no need to repeat it daily |

## Consequences

- ➕ A fund's intraday chart is now filled in even for days the collector was never running at all (not just started late) — up to the last 5 days.
- ➕ Same dashed/no-NAV limitation in the panel the user already knows from ADR 0012; consistent behavior, no new surprise in the UI.
- ➖ Intraday NAV and real-entity money flow still don't exist for these days — TSETMC has no endpoint for "NAV at a given past minute"; NAV is only ever queried live, and never comes with a past timestamp.
- ⚠️ The tested sample was 15 funds, not 334; if the rejection rate turns out higher than expected after running on all funds, the `tsetmc_backfill_funds_total{status="rejected"}` metric and the `note` column in `intraday_backfill_log` are the first places to look.
- ⚠️ Hira (in the sample) always came back empty; a few funds may never be backfillable, similar to the behavior seen in ADR 0012.
