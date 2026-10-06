# Financial Logic

<p class="lead">The metrics built from raw data: each one's precise definition, why it was chosen, and which question it answers for a trader or a portfolio manager. All formulas live in <code>domain/metrics.py</code> and have unit tests.</p>

<div class="kpis">
  <div class="kpi"><b>159</b><span>equity, index, sector and leveraged funds</span></div>
  <div class="kpi"><b>375T toman</b><span>estimated net asset value (end of 1 Mehr 1405)</span></div>
  <div class="kpi"><b>−0.5%</b><span>median premium (excluding leveraged funds)</span></div>
  <div class="kpi warn"><b>−18%</b><span>artificial "premium" of leveraged funds</span></div>
</div>

!!! info "Data on this page"
    The numbers on this page come from real TSETMC data at the close of the session on 1 Mehr 1405: the full list of 333 funds, NAV for all of them, and 400 days of history, captured with `scripts/capture_offhours.py` and run through the same service pipeline. "T toman" means trillion toman (10<sup>13</sup> Rials).

## Metrics

| Metric | Formula | Unit | Question it answers |
|---|---|---|---|
| **Daily return** | close ÷ previous close − 1 | % | What did the fund do today? |
| **Premium (NAV premium)** | close ÷ redemption NAV − 1 | % | How much more (or less) than asset value is the buyer paying? |
| **Net asset value (AUM)** | redemption NAV × units outstanding | Rial | How big is the fund? |
| **Share of fund market** | fund AUM ÷ total AUM | % | How much weight does the fund carry in the overall picture? |
| **Retail money inflow** | individual buy value − individual sell value | Rial | Where is retail money going, and where is it leaving? |
| **Retail buyer strength** | (individual buy value ÷ buyer count) ÷ (individual sell value ÷ seller count) | ratio | Are buyers bigger players than sellers, or the reverse? |
| **Turnover** | trade value ÷ net asset value | % | How liquid is the fund? Was today's trading unusual? |
| **Periodic return** | today's close ÷ origin close − 1, for 1 week, 1 month, 3 months and year-to-date | % | Which funds have trended better over the medium term? |

## Premium: The Most Important Metric for a Tradable Fund

An ETF has two prices: the **market price**, set by buyers and sellers, and **NAV**, the actual value of the assets behind each unit. The difference between the two is the premium:

- **Positive premium:** the buyer is paying more than the underlying assets are worth. This usually signals buying excitement, and a market maker or new unit issuance will typically close the gap.
- **Negative premium:** the fund's units trade below their asset value. This signals selling pressure, or, for certain funds, redemption restrictions.

The calculation is based on **redemption NAV**, not subscription NAV, because a seller who redeems their units gets exactly that amount — making it the floor value of a unit.

<figure class="diagram">
<img src="assets/diagrams/premium-by-type.svg" alt="Fund premium by type">
<figcaption>Figure 1 — Premium across all funds, broken down by type (real data). Equity, sector and index funds cluster around zero. Leveraged funds all sit around −18%: a structural artifact, not a buying opportunity.</figcaption>
</figure>

### Finding: Leveraged Fund NAV Isn't Comparable to Price

In real data, **7 of 9 leveraged funds** (Ahrom, Shetab, Bidar, Mowj, Narenj-e-Ahrom, Tavan, Jahesh) show a "premium" between −16.7% and −19.2%. This consistency across funds with different managers and holdings shows the cause lies in the **NAV definition**, not the market.

A leveraged fund has two unit classes: **preferred units** (investors with a guaranteed return) and **ordinary units** (the units actually traded on the exchange, which carry the leveraged return). The NAV published on TSETMC is not equal to the ordinary unit's value, so comparing the ordinary unit's price against it is meaningless.

!!! danger "Decision"
    `nav_premium()` returns **`null`** for leveraged funds, and the panel shows "not computable" instead of a number. Showing −18% to a trader would imply a buying opportunity that doesn't exist. These funds' net asset value is also shown with caution, labeled "approximate".

**Two funds, "Dara Yekom" (−34%) and "Palayesh" (−30%)**, also carry a large discount, but this one is real. Both are government-divestiture ETFs that have traded below NAV for years. They aren't excluded, but the market-wide aggregate is built from the **median** so these two large funds don't skew the overall picture (`robust_center`).

## Retail Money Flow and Estimated Value

During the trading day, TSETMC only provides the **volume** of individual and institutional trades, not their Rial value. Intraday value is estimated as follows:

```text
individual buy value ≈ individual buy volume × (total trade value ÷ total trade volume)
```

That is, volume multiplied by today's volume-weighted average price. After market close, this is replaced by the **official** figure from `GetClientTypeHistory`. Both versions are kept, and the `FLOW_VALUE_ESTIMATED` flag marks the estimated one. The daily money-flow chart shows past days with the official value and today labeled as "estimated".

!!! tip "Sanity check against real data"
    In the official history for "Atlas" on 1 Mehr: individual buys 7,768,744 + institutional buys 1,816,614 = **9,585,358** units, which exactly matches that day's total trade volume. The `client_volume_mismatch` check in [Data Quality](04-data-quality.md) is built on this same identity.

## Periodic Returns and the Jalali Calendar

Returns are computed from **official closing prices** over **calendar windows** (7, 30 and 91 days). Each window's origin is the last trading day **on or before** the origin date, so holidays don't throw off the calculation.

"Year-to-date" means from **1 Farvardin**, not January 1. The fiscal year for most Iranian capital-market funds and reports is the Jalali year. Date conversion uses the 33-year cycle algorithm for the Jalali calendar in `domain/jalali.py` (no external dependency, tested against Nowruz for 1402–1406 and the leap year 1403).

??? question "Why is return based on price rather than NAV?"
    TSETMC doesn't provide a daily NAV history — only the live NAV is published. Price-based return is what a trader actually realized. The service has stored each day's closing NAV in `fund_eod` since day one of collection, so NAV-based return becomes computable over time.

## Market-Level Aggregation

| Market metric | Aggregation method | Why |
|---|---|---|
| Total net asset value | Sum | An additive quantity |
| Total retail money inflow | Sum | An additive quantity |
| Market premium | **Median**, excluding leveraged funds | Robust against outlier funds (Dara Yekom, Palayesh) |
| Weighted market premium | AUM-weighted average, excluding leveraged funds | Shows where the market's money actually sits (next section) |
| Market breadth | Count of advancing, declining and unchanged funds | A weighted average is driven by a few large funds; breadth shows the general state |

### Premium: Median or Weighted? {#premium-median-or-weighted}

These two numbers answer different questions, and the panel shows both side by side:

- **Median:** how expensive or cheap is a "typical" fund? For a trader looking for a fund to buy.
- **Weighted (by net asset value):** on average, at what premium was each Rial invested in this market bought? For a portfolio manager looking at the market as a whole.

On real data from the close of the session on 1 Mehr 1405, the gap between these two was large:

<div class="kpis">
  <div class="kpi"><b>−0.5%</b><span>median premium, 150 funds</span></div>
  <div class="kpi warn"><b>−11.8%</b><span>weighted premium</span></div>
  <div class="kpi"><b>36.6%</b><span>Palayesh and Dara Yekom's share of net asset value</span></div>
  <div class="kpi"><b>−0.5%</b><span>weighted premium excluding those two funds</span></div>
</div>

Two large funds, **Palayesh** (−29.8%, 21.6% of total assets) and **Dara Yekom** (−33.9%, 15% of total assets), pull the weighted number down on their own. Without them, the weighted premium matches the median exactly. So "weighted premium −12%" means "these two privatization funds trade at a discount", not "the fund market is 12% cheap". That's why the panel's main tile shows the median, with the weighted number alongside it. The "market premium over time" chart plots both lines: if the gap between them changes, large funds are behaving differently from the rest of the market.

This chart's history is built from `fund_eod` (each day's closing NAV, from minute-level data). TSETMC doesn't provide NAV history, so the series starts from the first day the service collected data, and each session adds one more point.

## Implementation

- **SQL only retrieves data**, using `FINAL`, `LIMIT 1 BY` and `argMaxIf` over at most a few hundred thousand rows. **Python does the computing** (`analytics/service.py` and `domain/metrics.py`), because the formulas have unit tests in Python and the result set is small: one row per fund.
- The `fund_eod` table uses a materialized view to keep each fund's latest state per day. Only "last value" aggregations (`argMax`) are used, since they're robust against duplicate rows (replay, forward-fill). A `sum` aggregation over a `ReplacingMergeTree` source would double-count duplicates.
- Response time on real data (159 funds, 49K history rows) **without caching** is under 90 ms. Caching (ADR 0006) brings this down to a few milliseconds for the rest of that minute's requests.
