# Data Quality and Preprocessing

<p class="lead">After every fetch, before writing to the database, data completeness and correctness are checked. Every issue is either corrected using the information at hand or flagged, and both are recorded in the quality report.</p>

<div class="kpis">
  <div class="kpi"><b>10</b><span>checks per cycle</span></div>
  <div class="kpi"><b>13</b><span>quality flags per tick</span></div>
  <div class="kpi"><b>0</b><span>silent corrections</span></div>
  <div class="kpi"><b>3 ms</b><span>median validation time for 150 funds</span></div>
</div>

<figure class="diagram">
<img src="assets/diagrams/validation.svg" alt="Validation stages per cycle">
<figcaption>Figure 1 — Four groups of checks on each cycle's ticks, in order. Each check compares the current tick against market rules and against the same fund's previous tick.</figcaption>
</figure>

## Principles

<div class="grid cards two" markdown>

-   :material-eye-outline: __No correction is silent__

    ---

    Every change leaves two traces: a bit in that row's `quality_flags`, and a row in `data_quality_log` saying what was seen and what was done. The raw data also stays untouched in `raw_snapshots`.

-   :material-history: __Only with the information we have__

    ---

    Correction means carrying forward the last valid value (forward-fill), not interpolation. Interpolating volume or price means fabricating a trade that never happened, and for financial data that's worse than missing data.

-   :material-scale-balance: __Market rules, not generic statistics__

    ---

    The Tehran Stock Exchange has a daily price band. A price outside that band is **impossible**, and there's no need for a z-score or MAD. Generic statistical tests in a market with a price band either produce false alarms or miss real errors.

-   :material-bell-ring-outline: __Edge-triggered logging__

    ---

    Persistent conditions (stale NAV, missing fund, frozen feed) create exactly one log row **at the start of each occurrence**, not one every minute. The flag still lands on every affected tick. The report stays readable, and data filtering stays precise.

</div>

## Checks

| # | Check | Condition | Severity | Action | Flag |
|:-:|---|---|:-:|---|---|
| 1 | `missing_fund` | A fund on today's list isn't in the market watch | warn | Carry forward the previous tick (up to 30 minutes); otherwise drop | `FORWARD_FILLED` |
| 2 | `gap` | The gap between the current tick and the previous one exceeds one minute (during market hours) | warn | Build ticks for the missed minutes using the previous value; if over 30 minutes, it's left open | `FORWARD_FILLED` |
| 3 | `feed_stale` | The whole market watch's maximum `hEven` hasn't changed in 3 consecutive cycles | error | Flag on all ticks | `STALE_QUOTE` |
| 4 | `price_out_of_band` | Last or close price is outside the day's `[pMin, pMax]` | error | Replace with the previous tick's price; if none, keep it | `PRICE_OUT_OF_RANGE` |
| 5 | `ohlc_inconsistent` | High/low doesn't include open and last | warn | Recompute high and low | `RANGE_REPAIRED` |
| 6 | `cumulative_decrease` | Volume, value, count, or retail/institutional volume decreased relative to the previous tick of the same day | error | Keep the previous value (monotonicity enforcement) | `CUMULATIVE_DECREASE` |
| 7 | `client_volume_mismatch` | Sum of retail and institutional buy (or sell) differs from total volume by more than 2% | warn | Flag only | `CLIENT_VOLUME_MISMATCH` |
| 8 | `nav_missing` | The NAV request failed or had no value | warn | Carry forward the previous NAV along with its calculation time | `NAV_MISSING`, `NAV_CARRIED` |
| 9 | `nav_stale` | NAV calculation time is more than 20 minutes before the tick | info | Flag only | `NAV_STALE` |
| 10 | `nav_jump` | NAV change relative to the previous tick exceeds 10% | warn | Flag only; the value is untouched | `NAV_JUMP` |

All thresholds are configurable via environment variables (`VALIDATION_NAV_STALE_MINUTES`, `VALIDATION_NAV_JUMP_RATIO`, `VALIDATION_CLIENT_MISMATCH_RATIO`, `VALIDATION_MAX_GAP_FILL_MINUTES`, `VALIDATION_FEED_STALE_CYCLES`).

## Why these methods?

??? question "Why forward-fill and not linear interpolation?"
    If the collector is down from 10:02 to 10:04, we don't know what trades happened during those three minutes. Linearly interpolating cumulative volume manufactures trades with a uniform distribution that may never have occurred. Forward-fill just says "the last thing we saw was this", and the `FORWARD_FILLED` flag makes that explicit. Charts stay continuous, and analysis that needs precision can filter these rows out.

??? question "Why is an out-of-band price replaced with the previous price instead of being dropped?"
    Dropping a row means a hole in the time series, and the rest of that row's columns (NAV, retail/institutional) are lost too. The error is in just one column, so only that column is corrected. The original value is preserved in the raw response and can be reconstructed with `replay`.

??? question "Why does a retail/institutional mismatch only get flagged?"
    `ClientTypeAll` and the market watch are two separate endpoints and aren't captured at the exact same instant; a few seconds of difference between them is normal. Neither takes precedence over the other, so there's no basis for correction. The flag lets the retail-money-flow chart render these minutes faded.

??? question "Why isn't a NAV jump corrected?"
    A change of more than 10% within a few minutes is unlikely for an equity fund, but possible for a leveraged fund on a volatile day. It can also signal a corporate event (e.g. a unit split). The decision is left to the analyst, so it's only flagged.

## Gap-filling and edge logging, in practice

<figure class="diagram">
<img src="assets/diagrams/quality-timelines.svg" alt="Gap-filling and edge logging">
<figcaption>Figure 2 — Top: three missed minutes are filled with the value of the last real tick. Bottom: a stale NAV is flagged on every tick, but only one log row is created at the start of each occurrence.</figcaption>
</figure>

## Validator state

The validator is the only **stateful** part of the pipeline, since several checks need the previous tick:

| State | Used for | Managed by |
|---|---|---|
| Last tick per fund | Cumulative checks, NAV jump, gap-filling | Cleared at the start of each trading day |
| Active occurrences | Edge logging | Recovered from the last tick's flags |
| Feed `hEven` | Detecting a frozen feed | Counter of cycles without change |

**Restart:** if the collector restarts mid-day, on the first cycle the last tick for each fund is read back from ClickHouse (`LIMIT 1 BY ins_code`), and state resumes from there. Active occurrences are reconstructed from those same ticks' flags so duplicate log rows aren't created.

**replay:** runs with a fresh validator and processes cycles in time order, so the result matches what the live collector would have produced. That day's quality logs are cleared before replay to avoid duplicates.

## Daily report

```console
$ tsetmc-viewer quality --date 2026-09-26
Data quality — 2026-09-26
  cycles:        211  {'ok': 204, 'partial': 7}
  completeness:  99.61% of expected fund-minutes
  ticks:         31650
    FLOW_VALUE_ESTIMATED       31650  100.0%
    NAV_STALE                   2140    6.8%
    FORWARD_FILLED               123    0.4%
    ...
  issues:
    info   nav_stale                flagged                  96
    warn   missing_fund             forward_filled           11
    ...
```

!!! note "The numbers above are illustrative"
    The output format is real, but the numbers are estimates until the first full trading day, after which they'll be replaced with actual output.

The queries behind the report (`storage/repository.py → quality_report`):

```sql
-- Completeness: what fraction of expected "fund × minute" cells were actually received
SELECT sum(received_funds) / sum(expected_funds) FROM collection_runs WHERE toDate(tick) = today();

-- Share of each flag
SELECT countIf(bitAnd(quality_flags, 256) != 0) / count() AS forward_filled_ratio
FROM fund_ticks FINAL WHERE toDate(ts) = today();
```

## What is deliberately not done

- **Deleting suspect rows.** Deletion is irreversible; flagging is reversible.
- **Correcting against a second source.** Fipiran isn't available ([Data Sources](02-data-sources.md)), and there's no other source for intraday comparison.
- **Detecting official holidays from a calendar.** On a holiday, the `feed_stale` check shows the lack of fresh data. The holiday list is covered in [Next Steps](10-limitations.md#next-steps).
