# Data Sources

<p class="lead">What the provider supplies, what we build ourselves, and at which stage each is added to the database. Every number on this page comes from real responses recorded in <code>tests/fixtures</code> (2 Mehr 1405).</p>

<div class="kpis">
  <div class="kpi"><b>3,798</b><span>symbols in the market watch</span></div>
  <div class="kpi"><b>993</b><span>symbols in group 68 (funds and their options)</span></div>
  <div class="kpi"><b>432</b><span>tradable fund units</span></div>
  <div class="kpi"><b>1 s</b><span>response time for the full market watch with gzip</span></div>
</div>

## Provider: TSETMC

**Tehran Securities Exchange Technology Management Co. (TSETMC)** is the only source that publishes intraday trading data. This service uses its site's public API (`cdn.tsetmc.com/api`). This API has no official documentation and no versioning. For this reason, the raw response is always stored ([ADR 0003](adr/0003-raw-first-ingestion.md)), and parsers are tested against real recorded responses.

### Endpoints and real-world measurements

| endpoint | Purpose | Size | Response time | Frequency |
|---|---|--:|--:|---|
| `ClosingPrice/GetMarketWatch` | Full market watch: price, volume, value, 5 order-book levels | 3.5 MB (610 KB with gzip) | 1.0 s | every minute |
| `tsev2/data/MarketWatchPlus.aspx` (legacy version) | Same data, compressed CSV | 0.4 MB | 4.1 s | fallback option |
| `ClientType/GetClientTypeAll` | Retail/institutional buy and sell volume and count for all symbols | 500 KB | 2.2 s | every minute |
| `Fund/GetETFByInsCode/{ins}` | Redemption and issuance NAV, **with calculation time** | 120 B | 0.2–0.8 s | every minute, per fund |
| `ClosingPrice/GetClosingPriceInfo/{ins}` | **Symbol status** (`cEtaval`: allowed, allowed-halted, allowed-reserved, banned, …) and "under supervision" | 1 KB | 0.2 s | all funds on the first cycle of the day, then each fund every 5 minutes (one-fifth per minute) |
| `Instrument/GetInstrumentInfo/{ins}` | **Fund type**, number of units issued, ISIN, price threshold | 1 KB | 0.2 s | daily |
| `ClosingPrice/GetClosingPriceDailyList/{ins}/0` | Daily price history (up to 3,000 days) | 0.4–1 MB | 0.5–4 s | once + daily |
| `ClientType/GetClientTypeHistory/{ins}` | Daily retail/institutional history **with rial value** | 0.4–0.9 MB | 0.5–2.4 s | once + daily |
| `MarketData/GetMarketOverview/1` | Overall index, market status (open/closed) | 0.5 KB | 0.3 s | every minute |

!!! success "Correcting a measurement: gzip"
    The first measurement showed 15 seconds for the market watch, because the recording script wasn't sending the `Accept-Encoding: gzip` header. With compression (which httpx requests by default in the collector), the same response is 610 KB and arrives in 1 second. Fetching only the deltas (`hEven`/`RefID`) was also tested and works, but for the reasons given in [ADR 0006](adr/0006-caching.md), it wasn't adopted.

### Market watch field mapping

TSETMC's field names are abbreviations. This mapping was derived by comparing the market watch response with `GetClosingPriceInfo` for one symbol:

| TSETMC field | Our column | Meaning |
|---|---|---|
| `insCode` | `ins_code` | Internal symbol identifier |
| `lva` / `lvc` | `symbol` / `name` | Symbol / full name |
| `insID` | `isin` | International identifier (key linking to reference data) |
| `pdv` | `last_price` | Last traded price |
| `pcl` | `close_price` | Closing price |
| `pf` · `pmn` · `pmx` · `py` | `open` · `low` · `high` · `prev_close` | Open, low, high, and previous close |
| `qtj` · `qtc` · `ztt` | `volume` · `value` · `trade_count` | Volume, value (rials), and trade count |
| `pMax` · `pMin` | — | Day's allowed ceiling and floor (for validation) |
| `blDs[n].pmd/qmd/zmd` | `bid_*` | Bid level n: price, volume, order count |
| `blDs[n].pmo/qmo/zmo` | `ask_*` | Ask level n |
| `hEven` | — | Time of last symbol update (HHMMSS) |

### Identifying "equity funds"

TSETMC places funds in group 68, but **options written on funds** (such as "ضهرم…" and "طاطلس…") and **secondary boards** of the same funds (such as "سهامدار2") are also in that same group. The fund list is built every day via a four-stage funnel. The full logic is in [ADR 0007](adr/0007-fund-identity.md).

<figure class="diagram">
<img src="assets/diagrams/universe.svg" alt="Fund-identification funnel">
<figcaption>Figure 1 — The identification funnel for equity funds. The first three stages run using only market-watch data; the last stage needs a <code>GetInstrumentInfo</code> request per primary board, and for that reason runs once a day and is cached.</figcaption>
</figure>

A real example from five recorded funds:

| Symbol | `faraDesc` | Market | Units issued | Result |
|---|---|---|--:|---|
| اطلس | نوع صندوق : سهامی | Fara Bourse | 879,892,240 | ✅ Equity |
| آگاس | نوع صندوق : سهامی | Fara Bourse | 180,545,000 | ✅ Equity |
| دارا یکم | نوع صندوق: سهامي | Bourse | 497,825,920 | ✅ Equity (index) |
| اهرم | نوع صندوق: سهامي اهرمي | Bourse | 3,564,399,999 | ✅ Leveraged equity |
| یاقوت | نوع صندوق: در اوراق بهادار با درآمد ثابت | Bourse | 13,536,478,511 | ❌ Fixed income |

!!! note "Persian text normalization"
    TSETMC mixes Arabic letters (`ي`, `ك`) and Persian letters (`ی`, `ک`) interchangeably ("سهامی" and "سهامي" in the examples above). All text is normalized before comparison: unifying ی and ک, stripping extra ZWNJ characters, and trimming surrounding whitespace.

### Classification coverage across the whole market

After recording data for **all 333 primary fund boards** (2 Mehr 1405), it turned out that `faraDesc` is **empty for 81 funds**: 51 commodity funds and 30 others, 21 of which are equity or sector funds (such as "بانکو", "سیمان", and "آوان"). If classification had relied on `faraDesc` alone, these 21 funds would have been silently dropped from the analysis.

The fix came from a naming convention: funds' official names end with a **type letter**.

| Name suffix | Type | Example |
|:-:|---|---|
| `-س` | Equity | صندوق س.آوان ژرف آگاه-س |
| `-ب` | Sector | صندوق س.بخشي صنايع آسمان1-ب |
| `-د` | Fixed income | ص.س.درآمد ثابت آسال-د |
| `-م` | Mixed | صندوق تضمين ا.س. گيتي دماوند-م |

**This rule was validated before being used:** across 252 funds that have both a `faraDesc` and a name, name-only classification agrees with the official type in **250 cases (99.2%)**. The two remaining cases are fixed-income funds whose names carry no hint and fall into "other". So the rule's error never turns a non-equity fund into an equity one. This check exists as a test against the full real list in the repo (`test_name_convention_agrees_with_official_type`).

| Type | Count |
|---|--:|
| Equity | 80 |
| Sector | 62 |
| Leveraged | 9 |
| Index | 8 |
| **Total equity family (collected)** | **159** |
| Fixed income | 94 |
| Commodity | 52 |
| Mixed | 9 |
| Other (real estate, venture, private, etc.) | 19 |

## Fipiran: dropped

In the initial design, fund base data (type, manager, asset composition) was meant to come from `fund.fipiran.ir`. During recording, this domain's name **failed to resolve**. At the same time, it turned out TSETMC itself provides fund type and unit count. The result:

- ➕ One fewer external dependency and one fewer point of failure.
- ➖ Asset composition and the fund manager's name are currently unavailable. This is recorded under [Limitations](#limitations). The Fipiran client, written on day 1, was removed on day 6, since unused code only costs maintenance. It can be recovered from git history if needed.

## Provided data vs. processed data

=== "Provided by TSETMC"

    | Data | endpoint | Stage added | Table |
    |---|---|---|---|
    | Prices (last, close, open, low, high, previous) | Market watch | Minute cycle | `fund_ticks` |
    | Volume, value, trade count | Market watch | Minute cycle | `fund_ticks` |
    | First bid/ask level | Market watch | Minute cycle | `fund_ticks` |
    | Retail/institutional buy/sell volume and count | ClientTypeAll | Minute cycle | `fund_ticks` |
    | Redemption/issuance NAV and its calculation time | ETF | Minute cycle | `fund_ticks` |
    | Fund type, market, ISIN, unit count | InstrumentInfo | Daily sync | `funds` · `fund_daily` |
    | Daily retail/institutional rial value | ClientTypeHistory | End of day + backfill | `fund_daily` |
    | Daily price history | ClosingPriceDailyList | Initial backfill + daily | `fund_daily` |

=== "Processed by us"

    | Data | Formula / method | Stage | Table |
    |---|---|---|---|
    | **Fund classification** | ISIN + normalized `faraDesc` ← equity / leveraged / index / sector | Daily sync | `funds` |
    | **Net asset value (AUM)** | Redemption NAV × units issued | Minute cycle | view |
    | **Premium/discount** | (price ÷ redemption NAV) − 1 | Minute cycle | view |
    | **Intraday retail buy/sell value** | Retail volume × volume-weighted average price (value ÷ volume) — an estimate, replaced with the official figure at end of day | Minute cycle | `fund_ticks` |
    | **Retail money flow** | Retail buy value − retail sell value | Aggregate view | MV |
    | **Retail buyer power** | Per-capita buy ÷ per-capita sell | Aggregate view | MV |
    | **1-day / 1-week / 1-month / YTD return** | Based on NAV (asset return) and price (trader return) | Daily view | MV |
    | **Turnover** | Trade value ÷ net asset value | Daily view | MV |
    | **Share of the equity-fund market** | AUM ÷ total AUM | Daily view | MV |
    | **NAV freshness** | Difference between current time and NAV calculation time | Validation | `data_quality_log` |
    | **Quality flags** | Rules from the data-quality doc | Validation | `fund_ticks.quality_flags` |

## A trading day: what data, when

| Time (Tehran) | Stage | What's added | Table | Status |
|---|---|---|---|:-:|
| Before 09:00 | Daily sync | Fund list, type, market, unit count | `funds` · `fund_daily` | <span class="pill done">Day 2</span> |
| 09:00–12:30, every minute | Ingestion cycle | Raw response of all requests | `raw_snapshots` | <span class="pill done">Day 1</span> |
| | | Price, trades, NAV, retail/institutional, order book | `fund_ticks` | <span class="pill done">Day 2</span> |
| | | Overall index and market status | `market_ticks` | <span class="pill done">Day 2</span> |
| | Validation | Flags and quality report, data correction | `fund_ticks` · `data_quality_log` | <span class="pill done">Day 3</span> |
| On insert | Materialized View | Each day's closing state (price, value, NAV, money flow) | `fund_eod` | <span class="pill done">Day 4</span> |
| On request | Analytics layer (API) | Premium/discount, net asset value, money flow, buyer power, turnover, returns | — (computed in `analytics/`, cached in Redis) | <span class="pill done">Day 4</span> |
| 30 minutes after close | End-of-day completion | Official retail/institutional value, official closing price | `fund_history_daily` | <span class="pill done">Day 4</span> |
| After today's third cycle (or after close) | Backfilling missed minutes | Price, volume, value, and trade count before the collector was turned on, from trade-by-trade data and only when it's consistent with live ticks ([ADR 0012](adr/0012-intraday-backfill.md)) | `fund_ticks_backfill` · `intraday_backfill_log` | <span class="pill done">Post-day 7</span> |
| Startup outside market hours | bootstrap | 400-day history (or just the missing days), and a **closing snapshot** of the last session if it has no minute-level data | `fund_history_daily` · `fund_ticks` | <span class="pill done">Day 5</span> |
| Startup outside market hours | bootstrap | Minute-level data for the last 5 trading days during which the collector was never on, from price history, checked against the official end-of-day figure ([ADR 0013](adr/0013-session-backfill.md)) | `fund_ticks_backfill` · `intraday_backfill_log` | <span class="pill done">Post-day 7</span> |

!!! success "Resolved on day 4: leveraged-fund premium"
    In the recorded sample, "اهرم"'s price was 18% and "دارا یکم"'s was 34% **below** the redemption NAV. Checking all funds showed "دارا یکم"'s discount is real, but for leveraged funds the published NAV isn't comparable to the tradable unit's normal value. The premium/discount for these funds isn't computed. Details in [Financial Logic](05-financial-logic.md#finding-leveraged-fund-nav-isnt-comparable-to-price).

## Limitations

- Fund asset composition (equities, bonds, cash) and manager name don't exist in TSETMC.
- `ClientTypeAll` has no rial value. The intraday value is estimated and replaced with the official `ClientTypeHistory` figure at end of day. Both versions are stored.
### Today's trade-by-trade data: real-world measurement

The day-1 measurement (`Trade/GetTrade`: up to 22 MB and 110 s) was on a handful of symbols and **without** `Accept-Encoding: gzip` — the same mistake that had shown 15 seconds for the market watch. `scripts/probe_backfill.py` redid it correctly: 40 funds (the 10 most-traded plus 30 spanning the full range of trade counts), with gzip, 8 concurrent requests, at 12:17 on 4 Mehr 1405 (near the end of the session, i.e. peak response size):

| endpoint | Result | Errors | Extrapolated for 333 funds |
|---|---|:-:|---|
| `Trade/GetTrade/{ins}` | All of today's trades (time, price, volume, sequence number) | 0 of 40 | **2.3 MB**, about **10 seconds** with 8 concurrent requests (1.2 minutes sequentially) |
| `Trade/GetTradeHistory/{ins}/{date}/false` | For today: 502 or empty list | 27 of 40 | Not usable |
| `ClosingPrice/GetClosingPriceHistory/{ins}/{date}` | For today: 502 or empty list | 7 of 40 | Not usable |

- The most-traded fund ("موج", 19,282 trades) was **150 KB** compressed (3.9 MB uncompressed) and took 7.3 seconds; the median was 3 KB and 0.2 seconds. The day-1 number had been off by roughly a factor of 100, pessimistically.
- Under a load of 8 concurrent requests, TSETMC didn't slow down (ratio 1.01).
- **Warning:** in 6 of the 40 funds (such as "عیار", "هیرا", "جام طلا"), every trade's timestamp was recorded after 12:00, even though the session had been open since 9:00 ("هیرا": 14,443 trades in 34 seconds). Trade timing isn't reliable for these funds, and before building minute-level data from it, it must be cross-checked against our own live data.
- This endpoint only gives price, volume, and time. **Retail/institutional data, NAV, and the order book aren't in it**, so the retail-money-flow and NAV curves for periods before the collector was on cannot be reconstructed this way.

Based on this measurement, `GetTrade` was adopted for backfilling missed minutes, checking each fund against live ticks so the timing error above doesn't get persisted ([ADR 0012](adr/0012-intraday-backfill.md)).

### Minute-level history for past days: the hypothesis held up

The measurement above had only tested `GetTradeHistory` and `GetClosingPriceHistory` with `{date}` = **today**, and both returned 502 or an empty list — which was mistakenly recorded as "both unusable". Their name ("History") was the right clue: these two endpoints answer for a **past, closed day**, not today. With the VPN off and a real past date (29 Shahrivar 1405, `20260920`), the user re-tested on a sample of 15 funds:

| endpoint | Result with a past date | Conclusion |
|---|---|---|
| `Trade/GetTradeHistory/{ins}/{date}/false` | 12 of 15 funds returned `rows: 0` despite having thousands of recorded trades (یاقوت: 48,022 recorded trades, zero rows returned); no pattern between success/failure either | **Unreliable**; dropped |
| `ClosingPrice/GetClosingPriceHistory/{ins}/{date}` | 14 of 15 funds returned real rows (only هیرا was empty); extrapolated for 334 funds: **5.4 MB, about 7 seconds** in parallel | **Usable** |

`GetClosingPriceHistory` returns the same `DailyPriceRow` model (fields: `pDrCotVal`, `qTotTran5J`, `qTotCap`, `zTotTran`) that was already parsed for the 400-day bootstrap — the same daily feed, just with `hEven` (intraday time) added. Each row is itself a **cumulative total**, not a single trade, so there's no need to sum anything; it just needs to be sorted by time and sampled at each minute boundary.

Based on this finding, the last 5 trading days during which the collector was never on are now reconstructed at startup from this endpoint, checked against the official end-of-day figure instead of live ticks (which don't exist for a past day) — the same limitation as ADR 0012: no NAV, no retail/institutional data ([ADR 0013](adr/0013-session-backfill.md)).
