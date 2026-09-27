# syntax=docker/dockerfile:1.7
# Third-party images with this repo's configuration baked in.
#
# Configs are copied, not bind-mounted: a bind mount keeps the host's file
# mode and owner, so a file that is private on the host (0600) is unreadable
# for ClickHouse, Prometheus/Alertmanager (nobody) and Grafana (uid 472).
#
# Every stage follows the same three steps:
#   1. as root: copy the files and set modes (dirs 0755, files 0444) with
#      find + chmod. `COPY --chmod` also gives its mode to the directories
#      it creates, and a 0444 directory cannot be entered, so it is used
#      only where the target directory already exists (ClickHouse);
#   2. switch back to the user the image runs as;
#   3. prove that user can read the config, with the service's own checker
#      where one exists. A permission or syntax problem fails the build,
#      not the container at 3 a.m.
# docker-compose.yml builds one stage per service with `target`.

FROM clickhouse/clickhouse-server:24.8 AS clickhouse
# config.d already exists in the image, so COPY creates no directory and
# --chmod is safe here. A RUN step is avoided on purpose: this image's
# entrypoint manages its own user switch, and its USER must stay untouched.
COPY --chmod=0444 docker/clickhouse/prometheus.xml /etc/clickhouse-server/config.d/prometheus.xml

# ADR 0011: two replicas of this same image, behind clickhouse-keeper below,
# for the opt-in `ha-storage` compose profile. Same base and same COPY
# pattern as `clickhouse` above (config.d exists, so --chmod is safe); only
# the macros/cluster/keeper config is added. The two containers differ at
# runtime only in CLICKHOUSE_REPLICA_NAME (docker-compose), not in the image.
FROM clickhouse/clickhouse-server:24.8 AS clickhouse-ha
COPY --chmod=0444 docker/clickhouse/prometheus.xml /etc/clickhouse-server/config.d/prometheus.xml
COPY --chmod=0444 docker/clickhouse/macros.xml /etc/clickhouse-server/config.d/macros.xml
COPY --chmod=0444 docker/clickhouse/remote_servers.xml /etc/clickhouse-server/config.d/remote_servers.xml
COPY --chmod=0444 docker/clickhouse/zookeeper.xml /etc/clickhouse-server/config.d/zookeeper.xml

# ADR 0011: Keeper coordinates the two replicas above. This runs `clickhouse
# keeper` (the same binary, a different subcommand) instead of the separate
# clickhouse-keeper image, reusing this already-pulled, already-validated
# base rather than a second image whose default paths this repo would have
# to assume. No USER switch, for the same reason as `clickhouse` above; the
# destination directory does not exist yet, so it is made and chmod'd in one
# RUN rather than with `COPY --chmod` (which would also make the *directory*
# 0444 and unenterable — see the note atop this file). Keeper has no offline
# config checker (unlike promtool/amtool below), so unlike those stages there
# is no build-time proof step here; the `clusterize()` unit tests and the
# manual smoke test in ADR 0011 cover this instead.
FROM clickhouse/clickhouse-server:24.8 AS clickhouse-keeper
COPY docker/clickhouse/keeper_config.xml /tmp/keeper_config.xml
RUN mkdir -p /etc/clickhouse-keeper \
 && mv /tmp/keeper_config.xml /etc/clickhouse-keeper/keeper_config.xml \
 && chmod 0755 /etc/clickhouse-keeper \
 && chmod 0444 /etc/clickhouse-keeper/keeper_config.xml

FROM prom/prometheus:v2.55.1 AS prometheus
USER root
COPY monitoring/prometheus/prometheus.yml /etc/prometheus/prometheus.yml
COPY monitoring/prometheus/rules/tsetmc.yml /etc/prometheus/rules/tsetmc.yml
RUN find /etc/prometheus -type d -exec chmod 0755 {} \; \
 && find /etc/prometheus/prometheus.yml /etc/prometheus/rules -type f -exec chmod 0444 {} \;
USER nobody
RUN promtool check config /etc/prometheus/prometheus.yml

FROM prom/alertmanager:v0.27.0 AS alertmanager
USER root
COPY monitoring/alertmanager/alertmanager.yml /etc/alertmanager/alertmanager.yml
RUN chmod 0755 /etc/alertmanager && chmod 0444 /etc/alertmanager/alertmanager.yml
USER nobody
RUN amtool check-config /etc/alertmanager/alertmanager.yml

FROM grafana/grafana:11.2.2 AS grafana
USER root
COPY monitoring/grafana/provisioning/datasources/prometheus.yml /etc/grafana/provisioning/datasources/prometheus.yml
COPY monitoring/grafana/provisioning/dashboards/dashboards.yml /etc/grafana/provisioning/dashboards/dashboards.yml
# Outside /var/lib/grafana: that path is a volume, which would keep the first
# build's dashboards forever and hide every later change.
COPY monitoring/grafana/dashboards/ /etc/grafana/dashboards/
RUN find /etc/grafana/provisioning /etc/grafana/dashboards -type d -exec chmod 0755 {} \; \
 && find /etc/grafana/provisioning /etc/grafana/dashboards -type f -exec chmod 0444 {} \;
USER 472
RUN cat /etc/grafana/provisioning/datasources/prometheus.yml \
        /etc/grafana/provisioning/dashboards/dashboards.yml \
        /etc/grafana/dashboards/*.json >/dev/null
