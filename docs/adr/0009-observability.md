# ADR 0009 — Observability with Prometheus, Grafana, and Alertmanager

<div class="adr-meta"><span>Status: Accepted</span><span>Date: After day 7</span><span>Implementation: same day</span></div>

!!! abstract "Summary"
    Each service publishes its own metrics at `/metrics`, and ClickHouse uses its own built-in exporter. Prometheus scrapes them, Grafana shows dashboards defined in code, and Alertmanager hands alerts to a small relay in this same repo, which sends them in Persian to Bale, Telegram, or a webhook. Alert rules have unit tests, and a test guarantees that no dashboard queries a metric that doesn't exist.

## Context

Up to this point, service health was read from three places: `/health`, the logs, and Docker's healthcheck ([Testing and Hardening](../09-quality-engineering.md)). These answer "is it healthy right now?", but not "how long has it been broken?", "what's the trend?", or "who should be notified?". A service that collects unrecoverable data needs to notify a human of an outage **within minutes**.

Environment constraints:

- The server is in Iran: Telegram is usually unreachable, and image downloads are done over a VPN.
- The operator speaks Persian, and alert messages must be understandable without knowing PromQL.

## Decision

| Component | Choice | Reason |
|---|---|---|
| Metrics | `prometheus_client` inside each service | No separate exporter. All names and labels live in `telemetry.py` |
| ClickHouse | Built-in Prometheus exporter (`config.d`) | The database itself already exposes hundreds of precise metrics. No separate exporter needed |
| Scraping | Prometheus 2.55 with `dns_sd` for the collector | All collector instances (leader and standby) are discovered automatically |
| Display | Grafana 11 with dashboards provisioned from Python code | Reviewable, testable, no "dashboard that only exists on one system" |
| Alerting | Alertmanager + internal **alert-relay** | Grouping and dedup from Alertmanager; delivery to Bale and Persian text from the relay |
| Deployment | `monitoring` profile in compose | The core stack stays lightweight, and monitoring is added with one extra command |

## Rejected Options

| Option | Why not |
|---|---|
| **Alerting inside Grafana** | Its rules are stored as JSON or in Grafana's database and aren't unit-testable the way `promtool test rules` is |
| **Alertmanager's Telegram receiver** | Doesn't work inside Iran, always sends `parse_mode` (which Bale doesn't document), and the token would have to be written into a config file |
| **Separate exporters (clickhouse_exporter, etc.)** | ClickHouse already exposes its own metrics. Every exporter is one more image, one more port, one more failure point |
| **OpenTelemetry and Tempo/Loki** | Valuable for many services and tracing across them. Here we have four small services, and metrics plus logs are enough |
| **Logs and `/health` only** | No time series, and nobody gets notified |

## Consequences

- ➕ Any significant outage notifies the operator within minutes, in Persian, with a link to the fix guide ([Monitoring and Alerting](../11-monitoring.md#alerts-and-remediation-guide)).
- ➕ Alert rules have 8 test scenarios, run by CI via `promtool`. The CI smoke test also checks that Prometheus is scraping the services and that Grafana has all four dashboards.
- ➕ A Python test blocks any dashboard or alert that queries a nonexistent metric.
- ➖ Four extra images (Prometheus, Alertmanager, Grafana, and a relay built from the same service image). That's why monitoring is an optional profile.
- ⚠️ The relay is a single point of failure in the alert path. Undelivered messages stay in the logs, Alertmanager retries until it gets a 5xx, and Prometheus also scrapes the relay itself.

## Review: Configuration Baked Into the Image, Not Mounted {#config-baked-into-image-not-mounted}

**What happened:** The first run on the development machine stopped with `Access to file denied: /etc/clickhouse-server/config.d/prometheus.xml`, followed by every service stuck in `dependency failed to start`. Config files were handed to the container via bind mount, and a mount keeps the host file's permissions and owner. A file that's `0600` (owner-only) on the host isn't readable by ClickHouse (uid 101), Prometheus and Alertmanager (nobody), or Grafana (uid 472).

**Decision:** A `docker/config.Dockerfile` with one stage per service that copies the config into that service's own official image. Each stage has three steps: (1) as root, copy the files and fix permissions with `chmod` (directories `0755`, files `0444`); (2) switch back to the user the service actually runs as; (3) **as that same user**, read the config: `promtool check config` for Prometheus, `amtool check-config` for Alertmanager, and reading every file for Grafana. So a permission or syntax error stops the build, not the container. Compose builds each stage with `target`.

| | Bind mount | Baked into the image |
|---|---|---|
| Depends on host permissions, owner, or SELinux | Yes | No |
| Service has exactly the reviewed config | Only if nobody changed the file on the server | Yes; every change is a build |
| Cost of a config change | restart | `up -d --build` (a few seconds; the base layer is cached) |

**Related fixes:**

- **The first attempt with `COPY --chmod=0444` failed.** BuildKit applies that permission to the directories it creates too. A directory without the execute bit can't be opened by a non-root user, so Prometheus failed on `/etc/prometheus/rules` and Grafana on `/etc/grafana/dashboards` with `permission denied`. ClickHouse was unaffected because its `config.d` directory already existed in the base image; `--chmod` was kept there only. The main lesson was that permission correctness must be **proven at build time, as the actual service user**, not argued about. A test also checks that every stage (except ClickHouse) avoids `--chmod` and has a verification step after switching back to the service user.
- Previously the whole `rules/` directory was mounted, and `tsetmc_test.yml` (`promtool` test scenarios, not a rule) was also picked up by the `rules/*.yml` glob. Now only `tsetmc.yml` is in the image.
- Grafana dashboards moved from `/var/lib/grafana` to `/etc/grafana/dashboards`; `/var/lib/grafana` is a volume and kept the content of the first build forever.
