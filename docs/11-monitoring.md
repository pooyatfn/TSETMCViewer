# Monitoring and Alerting

<p class="lead">Three things should always be clear: whether the collector is fetching data, whether the API is responding to the panel, and whether ClickHouse is healthy. Each service publishes its own metrics, Prometheus scrapes them, Grafana displays them, and Alertmanager sends every problem — in Persian, with a link to this page's runbook — to Bale, Telegram, or any other webhook.</p>

<div class="kpis">
  <div class="kpi"><b>4</b><span>Grafana dashboards, defined as code</span></div>
  <div class="kpi"><b>16</b><span>alerts, each with a remediation guide on this page</span></div>
  <div class="kpi"><b>8</b><span>unit test scenarios for alert rules (promtool)</span></div>
  <div class="kpi"><b>0</b><span>secrets in config files; all in ‎.env</span></div>
</div>

<figure class="diagram">
<img src="assets/diagrams/monitoring.svg" alt="Monitoring and alerting architecture">
<figcaption>Figure 1 — each service exposes its own <code>/metrics</code> and no separate exporter is needed; ClickHouse also has its own built-in exporter. The orange line is the alert path.</figcaption>
</figure>

## Setup

```bash
docker compose --profile monitoring up -d        # Prometheus, Alertmanager, Grafana, alert-relay
```

| Address | What |
|---|---|
| <http://localhost:3000> | **Grafana** (username/password: `GRAFANA_USER` / `GRAFANA_PASSWORD`, default admin). The landing page is the "Overview" dashboard |
| <http://localhost:9090/alerts> | Prometheus: status of all alerts |
| <http://localhost:9093> | Alertmanager: active alerts, temporary silencing |

Monitoring is a separate **profile**: the main stack works fully without it, and someone who just wants the dashboard doesn't have to download three extra images (downloads from Docker Hub go through the VPN, see the [runbook](08-runbook.md)). All monitoring ports are bound only to `127.0.0.1`.

### Receiving Alerts in Bale

TSETMC is only reachable from Iranian IPs, so the server is usually in Iran. In that case Telegram isn't reachable, but **Bale** is, and Bale's bot API is Telegram-compatible:

1. Create a bot in Bale with `@botfather` and get its token.
2. Add the bot to the alert group or channel and find the chat id.
3. In `.env`, write:

    ```bash
    ALERT_BALE_TOKEN=123456:ABC...
    ALERT_BALE_CHAT_ID=987654321
    ```

4. `docker compose --profile monitoring up -d alert-relay`. The log should show `alert relay ready` with `"channels": ["bale"]`.

Telegram (`ALERT_TELEGRAM_*`) and any other webhook (`ALERT_WEBHOOK_URL`, e.g. n8n or a Slack/Mattermost bridge) are enabled the same way, and can be active at the same time. With no channel configured, alerts are only written to the alert-relay log.

!!! question "Why a relay instead of Alertmanager's own receivers?"
    Alertmanager's Telegram receiver always sends `parse_mode`, which isn't mentioned in Bale's bot documentation. The relay sends plain text, which both accept. Alertmanager also doesn't read environment variables, so the token would have to be written into the config file. The relay, like the other services, reads `.env`. Messages are also built from the rules' Persian annotations. The relay only returns an error to Alertmanager when **all** channels fail, so a retry doesn't resend a message that was already delivered.

A real message from the outage drill (see the [drill](#live-outage-drill) section):

```text
TSETMCViewer

[بحرانی] چرخه‌های دریافت پشت سر هم شکست می‌خورند
7 چرخه‌ی ناموفق پیاپی. شایع‌ترین علت: TSETMC از این IP در دسترس نیست (VPN روشن است).
دریافت داده · ساعت 01:28
راهنما: http://localhost:8001/11-monitoring/#collector-failing
```

<figure class="shot">
<img src="assets/screens/bale-alerts.webp" alt="Alert bot in Bale">
<figcaption>The same bot (<code>TSETMCViewerAlertBot</code>) in a real group in Bale: critical alert "Collector Unavailable" at 12:28 and its resolution at 12:38, then the "No Fresh Data Being Recorded" alert and its resolution — each message includes a link to this page's runbook.</figcaption>
</figure>

This real example also shows: the relay only sends the event, not every Alertmanager repeat (each message appears once for "fired" and once for "resolved"), and the runbook link appears in both.

## Metrics

All metrics are defined in a single file: `src/tsetmc_viewer/telemetry.py`. Label values are always bounded (endpoint name, status, path pattern like `/api/v1/funds/{ins_code}`), never a raw symbol code or URL, so the number of time series stays under control.

=== "collector"

    | Metric | Type | Meaning |
    |---|---|---|
    | `tsetmc_collector_cycles_total{status}` | counter | Cycles broken down by ok / partial / failed |
    | `tsetmc_collector_cycle_duration_seconds` | histogram | Duration of each cycle (budget: 60 seconds) |
    | `tsetmc_collector_last_success_timestamp_seconds` | gauge | Timestamp of the last cycle that wrote data |
    | `tsetmc_collector_failed_streak` | gauge | Number of consecutive failures |
    | `tsetmc_collector_funds_received` / `_expected` | gauge | Completeness of the latest cycle |
    | `tsetmc_collector_quality_issues_total{check,action}` | counter | Validator events ([data quality](04-data-quality.md)) |
    | `tsetmc_collector_rows_repaired_total{kind}` | counter | Rows completed or corrected |
    | `tsetmc_collector_leader` | gauge | 1 if this instance is the leader ([ADR 0010](adr/0010-high-availability.md)) |
    | `tsetmc_market_open` · `tsetmc_session_confirmed` | gauge | Calendar (including holidays) and session confirmation from TSETMC |
    | `tsetmc_source_requests_total{endpoint,outcome}` | counter | Final outcome of each request to TSETMC, after retries |
    | `tsetmc_source_request_duration_seconds{endpoint}` | histogram | Latency of each attempt |
    | `tsetmc_source_retries_total{endpoint}` | counter | Retry attempts |

=== "API"

    | Metric | Type | Meaning |
    |---|---|---|
    | `tsetmc_api_requests_total{route,method,status}` | counter | Requests broken down by route pattern |
    | `tsetmc_api_request_duration_seconds{route}` | histogram | Latency (SSE is excluded) |
    | `tsetmc_api_cache_total{result}` | counter | hit / miss / shared / not_modified |
    | `tsetmc_api_sse_clients` | gauge | Panels with a live open connection |
    | `tsetmc_api_database_unavailable_total` | counter | 503 responses due to a ClickHouse outage |

    With multiple workers, each process writes its metrics to a shared directory and `/metrics` returns the aggregate of all of them (prometheus_client's multiprocess mode).

=== "ClickHouse"

    ClickHouse's built-in exporter (`docker/clickhouse/prometheus.xml`, port 9363). Dashboards and alerts use these: `ClickHouseProfileEvents_SelectQuery` / `InsertQuery` / `FailedQuery` / `InsertedRows`, `ClickHouseMetrics_MemoryTracking` / `Merge`, and `ClickHouseAsyncMetrics_MaxPartCountForPartition` / `FilesystemMainPath*Bytes`.

!!! tip "A test catches the \"dashboard with no data\" problem"
    `tests/test_monitoring_config.py` compares every `tsetmc_*` metric name in the rules and dashboards against metrics that are actually registered. A dashboard that queries a nonexistent metric always shows "No data," which looks like calm and is exactly why it's the most dangerous kind of monitoring failure. The same test checks that every job the rules reference is actually scraped, that each alert on this page has a runbook link, and that the dashboards' JSON matches their code.

## Dashboards

Dashboards are defined in `monitoring/grafana/build_dashboards.py` and converted to JSON with `python monitoring/grafana/build_dashboards.py`. Grafana loads them at startup, and editing in the UI is disabled, because changes need to go through code and review.

!!! note "Configuration lives inside the image"
    Dashboards, Prometheus rules, Alertmanager configuration, and ClickHouse's `prometheus.xml` are copied into the image, not mounted from disk. After any change: `docker compose --profile monitoring up -d --build`. The reasoning is in [ADR 0009](adr/0009-observability.md#config-baked-into-image-not-mounted).

| Dashboard | Question | Panels |
|---|---|---|
| **Overview** | Is everything healthy? | Availability of collector, API, and ClickHouse; whether the market is open; age of the latest data; consecutive failures; **active alerts**; cycles and requests |
| **Data Ingestion** | Is data arriving complete and on time? | Leader, session confirmation, completeness, cycle outcome and duration, per-endpoint requests and latency, retries, quality events, and repaired rows |
| **API** | Is the panel fast and correct? | Requests per second, 5xx ratio, p95 latency, cache hit rate, live connections, 503s, per-route latency |
| **ClickHouse** | Does the database have room and headroom? | Availability, disk space, max parts in a partition, memory, queries and inserted rows, SELECT time, merges |

All dashboard queries were run against a real Prometheus. On the first run, 42 of 44 queries had data. The remaining two were metrics that only get a value on error (retries and 5xx) and showed "No data," which is different from "no errors at all." Now those two queries show zero when there are no errors, and after the outage drill all 45 queries had data.

## Alerts and Remediation Guide {#alerts-and-remediation-guide}

**Critical** alerts mean data is being lost or the user can't see something (repeats every 30 minutes). **Warning** means quality has degraded (repeats every 4 hours). Alertmanager replaces a root cause's downstream effects: when ClickHouse is down, "stale data" and "API errors" aren't sent separately, and when the collector fails repeatedly, "source errors" and "incomplete data" stay silent. So each incident is one message.

<figure class="shot half">
<img src="assets/screens/alertmanager.webp" alt="Alertmanager">
<figcaption>Alertmanager during the outage drill: a critical collector alert, grouped and ready to send to the relay.</figcaption>
</figure>

### Collector Unavailable {#collector-down}

**`TsetmcCollectorDown`** · critical · 2 minutes. Prometheus can't reach any collector instance. During market hours, every minute that passes means data that [can't be recovered](adr/0003-raw-first-ingestion.md).

```bash
docker compose ps collector            # Exited? unhealthy?
docker compose logs --tail=100 collector
docker compose up -d collector
```

### Collector Has No Leader {#no-leader}

**`TsetmcNoLeader`** · critical · 3 minutes. Collectors are up, but none holds the leadership lease. This usually means Redis was down and the instances haven't reacquired the lease yet (they retry every 15 seconds). Check `docker compose ps redis` and the `leadership` log.

### More Than One Leader {#split-brain}

**`TsetmcSplitBrain`** · warning · 5 minutes. Multiple instances are collecting data at the same time. Data doesn't get corrupted, because each row's key is (fund, minute) and ClickHouse deduplicates, but the load on TSETMC is multiplied. Common cause: Redis is erroring and each instance assumes it's the leader, by design ([ADR 0010](adr/0010-high-availability.md)).

### Cycles Failing Repeatedly {#collector-failing}

**`TsetmcCollectorFailing`** · critical · 1 minute. The most common cause on a dev machine is that **the VPN is on** and TSETMC rejects the foreign IP. Look for `source error` in the collector log. If the error is `ConnectError` or `403`, fix the [network](08-runbook.md#vpn-and-tsetmc-networking). The collector keeps going on its own; no restart is needed.

### Market Is Open but No Fresh Data Is Being Recorded {#data-stale}

**`TsetmcDataStale`** · critical · 2 minutes. The market is open right now (`tsetmc_market_open == 1`, a live signal — not `tsetmc_session_confirmed`, which stays 1 for the rest of the calendar day and remains 1 even after the market closes), but no cycle has written data for more than 5 minutes. If the collector isn't failing, writing to ClickHouse is usually the problem: check the `cycle crashed` logs.

### Incomplete Data {#low-completeness}

**`TsetmcLowCompleteness`** · warning · 10 minutes. Fewer than 90% of funds are received in each cycle. The "Data Ingestion" dashboard → "Requests by outcome" shows which endpoint is erroring (usually one fund's NAV).

### Data Source Errors {#source-errors}

**`TsetmcSourceErrors`** · warning · 10 minutes. More than 20% of requests fail even after retries. TSETMC is slow or unstable. If it persists, lower `HTTP_MAX_CONCURRENCY`.

### Slow Cycles {#slow-cycles}

**`TsetmcSlowCycles`** · warning · 15 minutes. p95 cycle duration has passed 45 seconds. With a 60-second budget, minutes will soon start slipping. The "per-endpoint latency" panel shows which request has slowed down ([cycle budget](01-architecture.md)).

### API Unavailable {#api-down}

**`TsetmcApiDown`** · critical · 2 minutes. `docker compose ps api` and `docker compose logs api`. The panel shows an error message in this state.

### API Errors {#api-errors}

**`TsetmcApiErrors`** · warning · 5 minutes. More than 5% of responses are 5xx. A ClickHouse outage returns 503 and has its own separate alert. A 500 means there's a bug: check the traceback in the API log.

### API Is Slow {#api-slow}

**`TsetmcApiSlow`** · warning · 10 minutes. p95 has passed 0.5 seconds (normally under 0.05). Check the "cache hit rate" panel: if it has dropped, Redis is probably down and every request is hitting ClickHouse ([load test](09-quality-engineering.md#load-test)).

### ClickHouse Unavailable {#clickhouse-down}

**`ClickHouseDown`** and **`ClickHouseUnavailableForApi`** · critical · 2 minutes. No data is being stored and the API returns 503. `docker compose logs clickhouse`. The most common causes are low memory and a full disk.

### Too Many Parts {#too-many-parts}

**`ClickHouseTooManyParts`** · warning · 10 minutes. Merges have fallen behind inserts. At 3000 parts, ClickHouse rejects inserts. In this service each cycle is one batch insert, so this alert usually means disk or CPU is low, or a large replay is running.

### Disk Filling Up {#disk-low}

**`ClickHouseDiskLow`** · warning · 10 minutes. Less than 10% free space. The biggest consumer is raw responses (about 120 MB/day with a 30-day TTL, [limitations](10-limitations.md#operational-limitations)). Shorten the TTL or grow the disk.

### Failed Queries {#failed-queries}

**`ClickHouseFailedQueries`** · warning · 10 minutes. Under normal operation there are no failed queries. Check the API log for `DatabaseError`. This usually means the schema doesn't match the code (a migration hasn't been run).

## Testing Alert Rules

Alert rules are code too, and have tests: `monitoring/prometheus/rules/tsetmc_test.yml`. Each scenario builds a synthetic time series and checks that the alert fires **exactly when expected**, that its Persian text is correct, and that it does **not** fire in a similarly harmless state (e.g. stale data while the market is closed).

```bash
promtool test rules monitoring/prometheus/rules/tsetmc_test.yml   # CI runs this exact command
```

These tests found a real bug: in the expression `A and B`, the alert value (`$value`) comes from the left-hand side. In the first version of the "stale data" alert, `session_confirmed` was on the left, and the message said "1 second ago." The order of the two sides was swapped.

## Live Outage Drill on a Real System {#live-outage-drill}

The whole chain was run once with real Prometheus 2.55 and Alertmanager 0.27 binaries. Two collectors, an API with two workers, and alert-relay operated on a copy of TSETMC's real responses:

| Step | Result |
|---|---|
| All targets | 7 of 7 `up`: two collectors, API, ClickHouse, relay, Prometheus, Alertmanager |
| Leadership | One collector was leader (`leader=1`), the other standby (`0`) |
| `docker stop` on the leader | The lease was released and the second instance became leader **about 2 seconds later** |
| TSETMC cut off | After 3 failed cycles, `TsetmcCollectorFailing` went from pending to firing, Alertmanager handed it to the relay, and the Persian message above was delivered to the webhook |
| TSETMC reconnected | `failed_streak` returned to zero and the alert resolved |
| Dashboard queries | All 45 queries had data against the real Prometheus |

!!! note "Grafana wasn't part of this drill"
    The Grafana image wasn't available in the build environment. The dashboards' JSON has been checked by tests and their queries were run against a real Prometheus, and the CI smoke test checks that all four dashboards load in Grafana. A screenshot of the dashboards will be taken on the user's first full run.
