# API

<p class="lead">The panel reads data only through this API. All responses are JSON, and the full contract (OpenAPI) is published automatically at <code>/docs</code> and <code>/redoc</code>.</p>

## Endpoints

| Path | Response | Used in panel for |
|---|---|---|
| `GET /api/v1/overview` | `Overview` | Top-of-page cards: AUM, money inflow, premium, breadth, total index |
| `GET /api/v1/funds` | `FundSnapshot[]` | Fund table and treemap |
| — | `FundSnapshot.status_kind` · `status_title` · `status_at` · `under_supervision` | Symbol status on TSETMC (`open` · `suspended` · `reserved` · `blocked` · `forbidden` · `unknown`) in every fund response; `Overview.not_trading` counts the funds in an abnormal state |
| `GET /api/v1/funds/{ins_code}?days=` | `FundDetail` | Fund page: status, returns, daily history for the last `days` days (calendar days, 5 to 4000, default 120) |
| `GET /api/v1/funds/{ins_code}/intraday` | `FundIntradayPoint[]` | Intraday chart of price, NAV and premium; minutes before the collector started are marked `backfilled: true` with no NAV or money flow ([ADR 0012](adr/0012-intraday-backfill.md)) |
| `GET /api/v1/market/flow` | `MarketFlowPoint[]` | Cumulative retail money inflow across the whole market through the day, alongside the index |
| `GET /api/v1/flows/daily?days=60` | `DailyFlow[]` | Daily money inflow broken down by fund type |
| `GET /api/v1/returns` | `FundReturns[]` | Heatmap of returns from 1 day to year-to-date |
| `GET /api/v1/premium/daily?days=120` | `PremiumPoint[]` | Market premium (median and weighted) at the close of each session |
| `GET /api/v1/premium/intraday` | `PremiumPoint[]` | Minute-by-minute market premium through the session |
| `GET /api/v1/calendar?year=1405` | `CalendarDay[]` | Official holidays, and announced and observed closures for a Jalali year |
| `GET /api/v1/sessions?limit=90` | `SessionInfo[]` | List of sessions `fund_ticks` has data for (most recent first); populates the session selector in the panel header |
| `GET /api/v1/quality` | Quality report | Data health indicator |
| `GET /api/v1/stream` | `text/event-stream` | Notifies the panel of a new tick |
| `GET /health` · `GET /api/v1/health` · `GET /api/v1/pipeline/runs` | — | API health and collector data freshness (the "stale data" banner in the panel) |
| `GET /metrics` | Prometheus text format | For Prometheus only; nginx does not expose it externally ([Monitoring](11-monitoring.md)) |

All analytical endpoints take an optional `?date=YYYY-MM-DD` parameter. **The default is the most recent trading session with data**, not today's date. The panel never goes empty on a holiday — it shows the previous session, labeled `is_live: false` with the Jalali date in `session_date_fa`. The session selector in the panel header sets this same parameter; its options come from `GET /api/v1/sessions`, marking "closing only" next to sessions that only have an end-of-day snapshot rather than a minute-level series (`has_intraday: false`).

```console
$ curl -s localhost:8000/api/v1/overview | jq
{
  "session_date": "2026-09-24",
  "session_date_fa": "1405/07/02",
  "is_live": false,
  "funds": 159,
  "total_aum": 3752367895747336,
  "ind_net_flow": 5738135670836,
  "median_premium": -0.0051,
  "advancers": 137, "decliners": 21, "unchanged": 1,
  "index_value": 7257043.42,
  "index_change": 0.0125,
  ...
}
```

## Conventions

<div class="grid cards two" markdown>

-   :material-currency-usd-off: __Amounts are Rial, integer__

    ---

    Conversion to toman or "T toman" happens only in the presentation layer. The API never returns a rounded number.

-   :material-percent-outline: __Ratios are plain fractions__

    ---

    `0.012` means 1.2%. A ratio that has no meaning is `null`, not zero (e.g. the premium of a leveraged fund, or turnover for a fund with no AUM).

-   :material-clock-time-four-outline: __Times carry a timezone__

    ---

    ISO 8601 with `+03:30`. Dates are Gregorian, each with a Jalali counterpart (`*_fa`) alongside it.

-   :material-flag-outline: __Quality flags by name__

    ---

    `quality_flags: ["NAV_STALE", "FLOW_VALUE_ESTIMATED"]`, not a bitmask. The panel uses these same names to dim suspect data.

</div>

## Caching and Headers

Every analytical response goes through the `cached_json` path ([ADR 0006](adr/0006-caching.md)):

| Header | Value | Meaning |
|---|---|---|
| `X-Tick` | `2026-09-26T10:41:00+03:30` | Which tick this response corresponds to |
| `X-Cache` | `hit` / `miss` | Served from Redis or from ClickHouse |
| `ETag` | `W/"…"` | Built from (path, parameters, tick) |
| `Cache-Control` | `private, max-age=N` | N = seconds remaining until the next tick |

```console
$ curl -sI localhost:8000/api/v1/funds | grep -iE 'x-cache|etag'
x-cache: miss
etag: W/"3f5a…"
$ curl -sI localhost:8000/api/v1/funds -H 'If-None-Match: W/"3f5a…"' | head -1
HTTP/1.1 304 Not Modified
```

If Redis is unavailable, the API serves straight from ClickHouse without erroring (`X-Tick: none`).

## Live Events (SSE)

```javascript
const events = new EventSource("/api/v1/stream");
events.addEventListener("tick", (e) => {
  const { tick, funds, status } = JSON.parse(e.data);
  refetchDashboard();          // responses are fresh at this point, and the server-side cache is ready too
});
```

| Frame | Timing |
|---|---|
| `event: hello` | On connect, with the latest tick |
| `event: tick` | After each minute's data is committed |
| `: keep-alive` | Every 15 seconds, so proxies don't close the connection |

**Why SSE instead of WebSocket?** The data flow is one-directional (server to browser). SSE runs over plain HTTP, the browser itself handles reconnection, and in FastAPI it's just a `StreamingResponse`.

## Performance

On real data (159 funds, 49K history rows), **without caching**:

| Endpoint | Size | Time |
|---|--:|--:|
| `/overview` | 0.4 KB | 78 ms |
| `/funds` | 108 KB (25 KB with gzip) | 32 ms |
| `/returns` | 29 KB | 68 ms |
| `/flows/daily?days=60` | 24 KB | 55 ms |
| `/funds/{ins}` | 11 KB | 85 ms |

## Day 5 Revision

- `index_change` in `overview` was changed from a **point value** (what TSETMC itself gives) to a **fraction** (0.0125 meaning +1.25%), to match the "ratios are plain fractions" convention. This inconsistency was caught the first time the panel displayed the number: the index tile showed "+8,963,791%". The `test_overview` test now checks this conversion.

## Post-Day-7 Revision

- `overview` has two new fields: `weighted_premium` (AUM-weighted market premium, [Financial Logic](05-financial-logic.md#premium-median-or-weighted)) and `holiday_today` (today's holiday name, official or observed).
- Three new endpoints: `premium/daily`, `premium/intraday` and `calendar`. All are cached by tick like the rest.
- The API runs with multiple workers. The cache is computed once across processes ([ADR 0010](adr/0010-high-availability.md)).
