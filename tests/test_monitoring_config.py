"""The monitoring stack is configuration; these tests keep it honest.

A dashboard or alert that queries a metric nobody exports shows "No data" forever —
the worst kind of monitoring bug, because it looks like calm. So: every tsetmc_*
metric used in rules and dashboards must exist in telemetry.py, every job must be
scraped, every runbook link must resolve, and generated dashboards must be current.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from prometheus_client import REGISTRY

from tsetmc_viewer import telemetry  # noqa: F401  (registers every metric)

ROOT = Path(__file__).resolve().parent.parent
MON = ROOT / "monitoring"
RULES = MON / "prometheus/rules/tsetmc.yml"
METRIC = re.compile(r"\b(tsetmc_[a-z_]+)")


def exported() -> set[str]:
    names: set[str] = set()
    for family in REGISTRY.collect():
        for sample in family.samples:
            names.add(sample.name)
        names.add(family.name)
        if family.type == "histogram":  # buckets appear only after an observation
            names |= {f"{family.name}_bucket", f"{family.name}_sum", f"{family.name}_count"}
        if family.type == "counter":
            names.add(f"{family.name}_total")
    return names


def queries() -> dict[str, str]:
    code = [line for line in RULES.read_text().splitlines() if not line.lstrip().startswith("#")]
    out = {"rules": "\n".join(code)}
    for path in (MON / "grafana/dashboards").glob("*.json"):
        out[path.name] = path.read_text()
    return out


def test_every_queried_metric_is_exported() -> None:
    available = exported()
    for source, text in queries().items():
        used = {m for m in METRIC.findall(text) if not m.startswith("tsetmc_viewer")}
        missing = used - available
        assert not missing, f"{source} queries unknown metrics: {sorted(missing)}"


def test_rule_jobs_are_scraped() -> None:
    scraped = {
        j["job_name"]
        for j in yaml.safe_load((MON / "prometheus/prometheus.yml").read_text())["scrape_configs"]
    }
    used = set(re.findall(r'job="([a-z-]+)"', queries()["rules"]))
    assert used <= scraped


def test_runbook_links_point_to_existing_anchors() -> None:
    doc = (ROOT / "docs/11-monitoring.md").read_text()
    anchors = set(re.findall(r"\{#([a-z0-9-]+)\}", doc))
    for runbook in re.findall(r'runbook: "docs/11-monitoring.md#([a-z0-9-]+)"', RULES.read_text()):
        assert runbook in anchors, f"docs/11-monitoring.md has no {{#{runbook}}}"


def test_alertmanager_sends_to_the_relay_service() -> None:
    am = yaml.safe_load((MON / "alertmanager/alertmanager.yml").read_text())
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    url = am["receivers"][0]["webhook_configs"][0]["url"]
    assert url == "http://alert-relay:9095/alertmanager"
    assert "9095" in compose["services"]["alert-relay"]["command"]


def test_generated_dashboards_are_up_to_date() -> None:
    spec = importlib.util.spec_from_file_location("build", MON / "grafana/build_dashboards.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, text in module.build().items():
        on_disk = (MON / "grafana/dashboards" / name).read_text()
        assert on_disk == text, (
            f"{name} is stale: run python monitoring/grafana/build_dashboards.py"
        )
        board = json.loads(text)
        assert all(
            p["datasource"]["uid"] == "prometheus" for p in board["panels"] if "datasource" in p
        )


@pytest.mark.skipif(shutil.which("promtool") is None, reason="promtool not installed (CI runs it)")
def test_alert_rules_unit_tests() -> None:
    result = subprocess.run(
        ["promtool", "test", "rules", str(MON / "prometheus/rules/tsetmc_test.yml")],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr


def test_configs_are_baked_into_images_not_mounted() -> None:
    """A bind mount keeps the host's file mode; a 0600 file breaks the container."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    for name, service in compose["services"].items():
        mounts = [v for v in service.get("volumes", []) if isinstance(v, str)]
        assert not [m for m in mounts if m.startswith(".")], f"{name} bind-mounts repo files"

    dockerfile = (ROOT / "docker/config.Dockerfile").read_text(encoding="utf-8")
    stages = dict(re.findall(r"^FROM \S+ AS (\S+)\n(.*?)(?=^FROM |\Z)", dockerfile, re.M | re.S))
    targets = {
        s["build"]["target"] for s in compose["services"].values() if "target" in s.get("build", {})
    }
    assert targets == set(stages)

    # Stages whose destination directory (config.d) already exists in the base
    # image, so `COPY --chmod` cannot make an unenterable directory there.
    existing_target_dir = {"clickhouse", "clickhouse-ha"}
    # Stages with no offline config checker to run as a build-time proof step
    # (Keeper has none, unlike promtool/amtool for Prometheus/Alertmanager).
    no_checker = {"clickhouse", "clickhouse-ha", "clickhouse-keeper"}

    for name, body in stages.items():
        for source in re.findall(r"^COPY (?:--chmod=\S+ )?(\S+) ", body, flags=re.MULTILINE):
            assert (ROOT / source).exists(), f"{name}: {source} does not exist"
        if name not in existing_target_dir:
            # COPY --chmod also applies to directories it creates: 0444 dirs cannot be entered.
            assert "--chmod" not in body, name
        if name not in no_checker:
            # The runtime user must prove it can read the config at build time.
            assert re.search(r"^USER (?!root)\S+\nRUN ", body, flags=re.MULTILINE), name
    assert "tsetmc_test.yml" not in dockerfile  # promtool scenarios are not rules
