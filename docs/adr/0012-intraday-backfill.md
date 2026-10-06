# ADR 0012 — Backfilling Missed Minutes from Trade-by-Trade Data

<div class="adr-meta"><span>Status: Accepted</span><span>Date: After Day 7</span><span>Based on the 4 Mehr 1405 measurement</span></div>

!!! abstract "Summary"
    If the collector starts late, the minutes before it started are reconstructed for **price, volume, value, and trade count** from today's trade-by-trade data (`Trade/GetTrade`); once a day, in about 10 seconds for all funds. Backfilled data is only stored when it **agrees** with the live ticks the collector wrote that same day, and it goes into a separate table so no analysis ever confuses it with live data. Real/legal-entity flow, NAV, and order book are not backfilled, since they are not in the trade-by-trade data.

## Context

- Per-minute data only existed from the moment the collector was started ([ADR 0003](0003-raw-first-ingestion.md)). A user who started the service at 11:30 would not see the 9:00–11:30 curve.
- The initial decision ("not used") was based on a Day 1 measurement: 22 MB and 110 seconds for a single symbol. That measurement was on a few symbols and without gzip.
- `scripts/probe_backfill.py` repeated it properly ([Results](../02-data-sources.md#todays-trade-by-trade-data-real-world-measurement)): 40 funds, layered, **zero errors**, extrapolating to **2.3 MB and about 10 seconds** for all funds. The other two endpoints returned 502 or an empty list for today.
- The same measurement showed two limitations: (1) trade-by-trade data only has time, price, and volume; (2) in 6 of the 40 funds, every trade's recorded time was after 12:00, even though the session had been open since 9:00.

## Decision

```text
After today's third successful cycle (in the background, so the minute loop doesn't fall behind)
or after market close if it hasn't run during the session:
  For every fund whose first live tick is after 9:01 and that has no decision recorded for today yet:
    Trade/GetTrade  →  raw response into raw_snapshots
    tape  = trades deduplicated, sorted by time, with a running cumulative sum
    check = each live tick's volume must fall between tape(ts − 60s) and tape(ts + 60s) (±1%)
    if ≥ 90% of live ticks agree  → minutes from 9:00 up to the first live tick go into fund_ticks_backfill
    otherwise                      → rejected in intraday_backfill_log, nothing is stored
```

| Decision | Reason |
|---|---|
| A **separate table** (`fund_ticks_backfill`), not `fund_ticks` | A backfilled row has no real/legal-entity flow, NAV, or order book. If it were filled with zeros in `fund_ticks`, the money-flow chart, the bubble chart, and every other analysis would be silently wrong |
| **Checking against our own live data** before storing | Trade time is unreliable for some funds. Rather than guessing which funds, every fund is checked against ticks we actually saw that same day |
| A **±60 second** window for checking | The tick for minute ts is captured a few seconds after ts, and the watcher itself may be a few seconds behind. A tighter window rejected correct funds; the real error (trades recorded after 12:00) is hundreds of times larger than that |
| Only **before the first live tick** | Live data is never replaced; backfill only fills the gap |
| After the **third** successful cycle | With no live tick there is nothing to check against; three ticks are enough to check, and it doesn't delay the backfill by much |
| In the **background** | It's about 10 seconds of requests; the minute loop must not wait for it. Both use the same cap of 8 concurrent requests |
| **Logging every decision** (`intraday_backfill_log`) | stored, rejected, no_trades, or error, with the count of minutes compared and matching. Re-running only retries errors |
| Only for **today** | `GetTrade` only has today's trades; past days cannot be backfilled this way |

In the panel, the backfilled part of the fund page's intraday chart is **dashed**, and its tooltip says "backfilled from trade-by-trade data". NAV and the bubble chart are empty in that section. Market-level charts (real-entity money flow) are unchanged.

## Rejected Options

| Option | Why not |
|---|---|
| **A queue (Celery/RQ) with multiple workers** | With 10 seconds of work per day, a queue would just be another service to maintain. `asyncio.gather` with the same semaphore is enough |
| **Writing into `fund_ticks` with a quality flag** | Every query that reads money flow or NAV would need to know about the flag; one forgotten query means a wrong number in the panel |
| **Trusting trade time without checking** | The real measurement showed it's wrong for about 15% of funds |
| **`GetClosingPriceHistory` or `GetTradeHistory`** | Returned 502 or an empty list for today |

## Consequences

- ➕ Starting the collector mid-session no longer means losing the morning's price curve.
- ➕ Every backfilled row is traceable: the raw response in `raw_snapshots` and the decision in `intraday_backfill_log`.
- ➖ Real-entity money flow and NAV before the collector was started still do not exist. This is a data-source limitation, not something this solution can fix.
- ⚠️ If the collector is started after market close, there is only one live point (the closing snapshot) to check against; the check is weaker, but it still catches the "trades recorded after 12:00" error.
- ⚠️ The thresholds (±1%, 90% of ticks) came from a single day's measurement. The rejected count in the log and the `tsetmc_backfill_funds_total{status}` metric are where to look; if correct funds start being rejected, these numbers are the first sign.

## Review: the "Rejected Option" Was Only Rejected for Today

The "Rejected Options" table above says `GetClosingPriceHistory`/`GetTradeHistory` returned 502 or an empty list for today — this is still true and unchanged (the ADR text is not rewritten). But that measurement was only done with `{date}` = today; it was retested with a real past date (by the user, 5 Mehr 1405), and `GetClosingPriceHistory` returned real data for 14 of 15 funds. In other words, rejecting this endpoint was only correct **for today**, not for past days. This finding led to a new, separate decision, not a rewrite of this one: [ADR 0013](0013-session-backfill.md).
