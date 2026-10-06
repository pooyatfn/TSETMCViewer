# Limitations and Next Steps

<p class="lead">The service was built in 7 days, and every choice had a cost. This page says plainly what it doesn't know or doesn't do, which numbers should be read with caution, and — had there been more time — in what order and at what cost it would have been completed.</p>

!!! abstract "Summary"
    The main limitations come from the **data source**, not the architecture: TSETMC doesn't provide fund asset composition, a holiday calendar, or the intraday rial value of retail/institutional flow. Minute-level data only exists when the collector was running during the session. The architecture (raw-first data, versioned migrations, a tick-aware cached API) was chosen so that each of the next steps can be added **without a rewrite**.

## Data limitations

| Limitation | Effect | What we did |
|---|---|---|
| **Retail money flow and NAV only exist from when the collector was on** | If the collector starts mid-session, price and volume for the preceding minutes are reconstructed from trade-by-trade data, but retail money flow, NAV, and the premium/discount for those minutes don't exist (they're not in the trade-by-trade feed). Days when the collector was never on have no intraday curve (`GetTrade` only covers today). For funds whose trade timing doesn't match live ticks, nothing is reconstructed | Checked reconstruction ([ADR 0012](adr/0012-intraday-backfill.md)), a closing snapshot for each session ([ADR 0004](adr/0004-scheduling.md#day-5-review-startup-outside-market-hours)). The reconstructed portion is dashed |
| **Intraday retail/institutional rial value is estimated** | Minute-level money flow = volume × average price. Usually close, but not official | Flag `FLOW_VALUE_ESTIMATED`, a faded column with * in the dashboard, and replacement with the official figure after market close |
| **Leveraged-fund NAV isn't comparable to a normal unit** | Premium/discount isn't computed for leveraged funds. Their net asset value is approximate | Premium/discount `null` and "not computable" in the dashboard ([Financial Logic](05-financial-logic.md#finding-leveraged-fund-nav-isnt-comparable-to-price)) |
| **Unit count updates once a day** | Issuance and redemption during the day aren't reflected in net asset value | Sync before market open, and documenting this |
| **Asset composition and fund manager aren't available** | It can't be said what percentage of equities an "equity" fund actually holds | [Data Sources](02-data-sources.md#limitations). An alternative source (Codal filings) is in the next steps |
| **Lunar holidays are only listed for 1405** | For later years, the list must be updated each year from the official calendar | Solar holidays follow a fixed rule. The session guard detects and logs no-trade days on its own ([ADR 0004](adr/0004-scheduling.md#post-day-7-review-holiday-calendar-and-multiple-instances)) |
| **Fund classification has 2 ambiguous cases out of 252** | Two funds might be in the wrong type | Source precedence and a test across all 333 funds ([ADR 0007](adr/0007-fund-identity.md)) |

## Analytical limitations

- **Returns are price-based, not total return on NAV.** For equity funds that don't distribute cash dividends the difference is negligible, but it isn't precise for comparison with other funds.
- **The only risk metric is volatility.** Annualized volatility is computed in the [dashboard](06-dashboard.md#9-risk-and-trailing-90-day-return); maximum drawdown, beta against the overall index, and tracking error for index funds are not yet. The needed data (400 days of history) exists — there just wasn't time.
- **No benchmark comparison.** Fund returns aren't shown against the overall index or an equal-weight index.
- **Market-wide premium/discount is a median.** The median is robust to a couple of outlier funds, but it doesn't account for large funds' weight. A weighted version (based on net asset value) could be shown alongside it.

## Operational limitations

| Limitation | Risk | Suggested fix |
|---|---|---|
| All services on a single host | There's multi-collector and multi-worker support for the API ([ADR 0010](adr/0010-high-availability.md)), and ClickHouse can run two replicated instances ([ADR 0011](adr/0011-clickhouse-replication.md), optional); but everything is on one host, so if that host goes down, the whole system stops | Redis Sentinel and a real multi-host deployment |
| The dashboard only shows sessions `fund_ticks` has data for | Minute-level data for past days isn't deleted (`fund_ticks` has no TTL; only raw responses are deleted after 30 days). The session selector in the dashboard header (`GET /api/v1/sessions`) shows any session with at least one recorded snapshot. As of post-day 7, this also includes the last 5 trading days during which the collector was never on (reconstructed, [ADR 0013](adr/0013-session-backfill.md)); beyond that, only days that were actually collected are listed | Done |
| No authentication | The API and dashboard are designed for an internal network. ClickHouse is only open on `127.0.0.1` | A reverse proxy with authentication before any public release |
| Grafana hasn't been seen against a real session's data | The dashboards have been checked with tests and by running their queries against real Prometheus, but a screenshot of them hasn't been taken yet | The first full run on the user's system ([Monitoring](11-monitoring.md)) |
| Raw data volume | Each cycle is about 4.4 MB of raw response (0.6 MB compressed in ClickHouse), roughly 120 MB per day. A 30-day TTL keeps the cap around 4 GB | The TTL is configurable. For long-term retention, move to object storage |
| Backups | Not configured. Clean data can be reconstructed from raw data for **the last 30 days**, but not beyond that | `clickhouse-backup` or a daily volume snapshot |

!!! note "What wasn't observed during the project window"
    - Intraday charts over one **full real session**: the service wasn't running on the user's system during any session. Their logic has been checked with synthetic data and tests ([Dashboard](06-dashboard.md)).
    - Running the **CI smoke test** on GitHub: the workflow file has been checked with actionlint, and three other jobs have been run against a clean copy of the repo. The smoke test will run for the first time on the first push.

## Next Steps {#next-steps}

In order of value to the trader and portfolio manager, along with an effort estimate (small: under one day, medium: 1–3 days, large: more). Five items were completed after day 7:

| # | Step | Value | Effort | Status |
|:-:|---|---|:-:|:-:|
| 1 | Official holiday calendar | Removes meaningless data on holidays | Small | <span class="pill done">Done</span> [ADR 0004](adr/0004-scheduling.md#post-day-7-review-holiday-calendar-and-multiple-instances) |
| 2 | Risk metrics and benchmark comparison | Understanding "return for how much risk" | Medium | <span class="pill done">Done (annualized volatility, 90 days)</span> [Dashboard](06-dashboard.md#9-risk-and-trailing-90-day-return) — max drawdown and beta not yet |
| 3 | Weighted premium and market premium time series | Seeing the trend of euphoria or fear | Small | <span class="pill done">Done</span> [Financial Logic](05-financial-logic.md#premium-median-or-weighted) |
| 4 | Prometheus metrics, Grafana, and alerting | Fast visibility into failures | Small | <span class="pill done">Done</span> [Monitoring](11-monitoring.md) |
| 5 | Asset composition from Codal's monthly filings | Answers "what does this fund actually hold?" | Large | <span class="pill todo">Next</span> a new source in `sources/` and migration `0006` |
| 6 | Personal alerts (premium crossed X, large outflow) | A trader's everyday tool | Medium | <span class="pill todo">Next</span> the alert relay path is now ready |
| 7 | Collector leader lock and multiple API workers | Availability | Medium | <span class="pill done">Done</span> [ADR 0010](adr/0010-high-availability.md) |
| 8 | ClickHouse with `ReplicatedMergeTree` (two replicas, one Keeper) | Data survives the failure of one replica | Medium | <span class="pill done">Done (on a single host)</span> [ADR 0011](adr/0011-clickhouse-replication.md) |
| 9 | Real multi-host HA (separate hosts, Redis Sentinel, multiple Keepers) | Staying up through the failure of one **server** | Large | <span class="pill todo">Next</span> ADR 0011 explains exactly why not right now |
| 10 | Session selector in the dashboard | Viewing past sessions without touching the database | Small | <span class="pill done">Done</span> [Dashboard](06-dashboard.md) · `GET /api/v1/sessions` |
| 11 | Minute-level data for past days (not just today) | A complete intraday chart even for days the collector wasn't on | Medium | <span class="pill done">Done (last 5 days)</span> [ADR 0013](adr/0013-session-backfill.md) |
