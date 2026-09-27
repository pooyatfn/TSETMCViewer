"""Grafana dashboards as code: `python monitoring/grafana/build_dashboards.py`.

Writes monitoring/grafana/dashboards/*.json, which Grafana provisions on start.
A test (tests/test_monitoring_config.py) fails if the JSON is out of date or if a
panel queries a metric that the services do not export.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).parent / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}
W = 24  # grid width


class Board:
    def __init__(self, uid: str, title: str, description: str) -> None:
        self.uid, self.title, self.description = uid, title, description
        self.panels: list[dict[str, Any]] = []
        self.y = 0
        self.x = 0
        self.row_h = 0

    def _place(self, w: int, h: int) -> dict[str, int]:
        if self.x + w > W:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        pos = {"x": self.x, "y": self.y, "w": w, "h": h}
        self.x += w
        self.row_h = max(self.row_h, h)
        return pos

    def row(self, title: str) -> None:
        if self.x:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        self.panels.append(
            {"type": "row", "title": title, "collapsed": False,
             "gridPos": {"x": 0, "y": self.y, "w": W, "h": 1}, "id": len(self.panels) + 1}
        )  # fmt: skip
        self.y += 1

    def _panel(self, kind: str, title: str, desc: str, w: int, h: int, **extra: Any) -> None:
        self.panels.append(
            {"type": kind, "title": title, "description": desc, "datasource": DS,
             "gridPos": self._place(w, h), "id": len(self.panels) + 1, **extra}
        )  # fmt: skip

    def stat(
        self, title: str, expr: str, desc: str = "", *, unit: str = "short", w: int = 4,
        thresholds: list[tuple[float | None, str]] | None = None, mappings: list[Any] | None = None,
    ) -> None:  # fmt: skip
        steps = [{"value": v, "color": c} for v, c in (thresholds or [(None, "green")])]
        self._panel(
            "stat", title, desc, w, 4,
            targets=[{"refId": "A", "expr": expr, "datasource": DS, "instant": True}],
            fieldConfig={"defaults": {"unit": unit, "mappings": mappings or [],
                                      "thresholds": {"mode": "absolute", "steps": steps}},
                         "overrides": []},
            options={"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                     "graphMode": "none", "textMode": "value"},
        )  # fmt: skip

    def series(
        self, title: str, targets: list[tuple[str, str]], desc: str = "", *, unit: str = "short",
        w: int = 12, h: int = 8, stack: bool = False, min0: bool = True,
    ) -> None:  # fmt: skip
        self._panel(
            "timeseries", title, desc, w, h,
            targets=[{"refId": chr(65 + i), "expr": e, "legendFormat": leg, "datasource": DS}
                     for i, (e, leg) in enumerate(targets)],
            fieldConfig={"defaults": {
                "unit": unit, "min": 0 if min0 else None,
                "custom": {"lineWidth": 2, "fillOpacity": 10 if stack else 0,
                           "stacking": {"mode": "normal" if stack else "none"},
                           "showPoints": "never"}},
                "overrides": []},
            options={"legend": {"displayMode": "list", "placement": "bottom"},
                     "tooltip": {"mode": "multi"}},
        )  # fmt: skip

    def alerts(self, title: str, w: int = 24, h: int = 7) -> None:
        self._panel(
            "alertlist", title, "هشدارهای فعال Alertmanager/Prometheus", w, h,
            options={"alertInstanceLabelFilter": "", "showInstances": True, "maxItems": 20,
                     "sortOrder": 1, "stateFilter": {"firing": True, "pending": True},
                     "viewMode": "list", "groupMode": "default", "datasource": "prometheus"},
        )  # fmt: skip

    def json(self) -> dict[str, Any]:
        return {
            "uid": self.uid, "title": self.title, "description": self.description,
            "tags": ["tsetmc-viewer"], "timezone": "Asia/Tehran", "schemaVersion": 39,
            "refresh": "30s", "time": {"from": "now-6h", "to": "now"}, "editable": True,
            "graphTooltip": 1, "panels": self.panels, "templating": {"list": []},
            "annotations": {"list": []}, "links": [
                {"title": "داشبوردهای TSETMCViewer", "type": "dashboards",
                 "tags": ["tsetmc-viewer"], "asDropdown": True}],
        }  # fmt: skip


UP = [(None, "red"), (1, "green")]


def quantile(q: float, histogram: str, window: str, by: str = "") -> str:
    """PromQL for a quantile of a histogram, summed across instances and workers."""
    labels = ", ".join(filter(None, ["le", by]))
    return f"histogram_quantile({q}, sum by ({labels}) (rate({histogram}_bucket[{window}])))"


YES_NO = [{"type": "value", "options": {"0": {"text": "خیر"}, "1": {"text": "بله"}}}]


def overview() -> Board:
    b = Board("tsetmc-overview", "TSETMCViewer · نمای کلی", "سلامت کل سرویس در یک نگاه")
    b.stat("collector", 'count(up{job="collector"} == 1) or vector(0)', "نمونه‌های در دسترس",
           thresholds=UP)  # fmt: skip
    b.stat("API", 'max(up{job="api"}) or vector(0)', thresholds=UP, mappings=YES_NO)
    b.stat("ClickHouse", 'max(up{job="clickhouse"}) or vector(0)', thresholds=UP, mappings=YES_NO)
    b.stat("بازار باز است", "max(tsetmc_market_open)", "طبق تقویم (با تعطیلات)",
           mappings=YES_NO, thresholds=[(None, "blue")])  # fmt: skip
    b.stat("عمر آخرین داده", "time() - max(tsetmc_collector_last_success_timestamp_seconds)",
           "ثانیه از آخرین چرخه‌ی موفق", unit="s",
           thresholds=[(None, "green"), (180, "orange"), (300, "red")])  # fmt: skip
    b.stat("شکست پیاپی", "max(tsetmc_collector_failed_streak)",
           thresholds=[(None, "green"), (1, "orange"), (3, "red")])  # fmt: skip
    b.alerts("هشدارهای فعال")
    b.series("چرخه‌ها در دقیقه", [
        ('sum by (status) (rate(tsetmc_collector_cycles_total[5m])) * 60', "{{status}}")],
        stack=True)  # fmt: skip
    b.series("درخواست‌های API در ثانیه",
             [('sum by (status) (rate(tsetmc_api_requests_total[5m]))', "{{status}}")],
             unit="reqps", stack=True)  # fmt: skip
    return b


def collector() -> Board:
    b = Board(
        "tsetmc-collector", "TSETMCViewer · دریافت داده", "حلقه‌ی دقیقه‌ای، منبع TSETMC و کیفیت"
    )
    b.row("وضعیت")
    b.stat("رهبر", "sum(tsetmc_collector_leader)", "تعداد نمونه‌هایی که lease را دارند؛ باید ۱ باشد",
           thresholds=[(None, "red"), (1, "green"), (2, "orange")])  # fmt: skip
    b.stat("جلسه تأیید شد", "max(tsetmc_session_confirmed)", "TSETMC معاملات امروز را نشان می‌دهد",
           mappings=YES_NO, thresholds=[(None, "blue")])  # fmt: skip
    b.stat("کامل بودن", "min(tsetmc_collector_funds_received / tsetmc_collector_funds_expected)",
           unit="percentunit",
           thresholds=[(None, "red"), (0.9, "orange"), (0.98, "green")])  # fmt: skip
    b.stat("صندوق‌ها", "max(tsetmc_collector_funds_received)", "در آخرین چرخه")
    b.stat("عمر آخرین داده", "time() - max(tsetmc_collector_last_success_timestamp_seconds)",
           unit="s", thresholds=[(None, "green"), (180, "orange"), (300, "red")])  # fmt: skip
    b.stat("شکست پیاپی", "max(tsetmc_collector_failed_streak)",
           thresholds=[(None, "green"), (1, "orange"), (3, "red")])  # fmt: skip
    b.row("چرخه‌ها")
    b.series("نتیجه‌ی چرخه‌ها (در دقیقه)",
             [('sum by (status) (rate(tsetmc_collector_cycles_total[5m])) * 60', "{{status}}")],
             stack=True)  # fmt: skip
    b.series("مدت چرخه", [
        (quantile(0.5, "tsetmc_collector_cycle_duration_seconds", "10m"), "میانه"),
        (quantile(0.95, "tsetmc_collector_cycle_duration_seconds", "10m"), "صدک ۹۵"),
    ], "بودجه‌ی هر چرخه ۶۰ ثانیه است", unit="s")  # fmt: skip
    b.row("منبع داده (TSETMC)")
    b.series("درخواست‌ها بر اساس نتیجه", [
        ('sum by (outcome) (rate(tsetmc_source_requests_total[5m]))', "{{outcome}}")],
        unit="reqps", stack=True)  # fmt: skip
    b.series("تأخیر هر endpoint (صدک ۹۵)", [
        (quantile(0.95, "tsetmc_source_request_duration_seconds", "10m", "endpoint"),
         "{{endpoint}}")],
        unit="s")  # fmt: skip
    b.series("تلاش دوباره (retry)", [
        ('sum by (endpoint) (rate(tsetmc_source_retries_total[5m])) * 60', "{{endpoint}}"),
        ("sum(rate(tsetmc_source_retries_total[5m])) * 60 or vector(0)", "همه")],
        "در دقیقه؛ خالی یعنی هیچ درخواستی دوباره تلاش نشده است")  # fmt: skip
    b.row("کیفیت داده")
    b.series("رخدادهای اعتبارسنجی (در دقیقه)", [
        ('sum by (check) (rate(tsetmc_collector_quality_issues_total[10m])) * 60', "{{check}}")],
        stack=True)  # fmt: skip
    b.series("ردیف‌های اصلاح‌شده (در دقیقه)", [
        ('sum by (kind) (rate(tsetmc_collector_rows_repaired_total[10m])) * 60', "{{kind}}")],
        stack=True)  # fmt: skip
    return b


def api() -> Board:
    b = Board("tsetmc-api", "TSETMCViewer · API", "درخواست‌ها، تأخیر، کش و اتصال‌های زنده")
    b.stat("درخواست در ثانیه", "sum(rate(tsetmc_api_requests_total[5m]))", unit="reqps")
    b.stat("خطای ۵xx", '(sum(rate(tsetmc_api_requests_total{status=~"5.."}[5m])) or vector(0)) '
           '/ sum(rate(tsetmc_api_requests_total[5m]))', unit="percentunit",
           thresholds=[(None, "green"), (0.01, "orange"), (0.05, "red")])  # fmt: skip
    b.stat("تأخیر صدک ۹۵", "histogram_quantile(0.95, sum by (le) "
           "(rate(tsetmc_api_request_duration_seconds_bucket[5m])))", unit="s",
           thresholds=[(None, "green"), (0.2, "orange"), (0.5, "red")])  # fmt: skip
    b.stat("نرخ استفاده از کش", 'sum(rate(tsetmc_api_cache_total{result!="miss"}[10m])) '
           '/ sum(rate(tsetmc_api_cache_total[10m]))', "hit + shared + 304",
           unit="percentunit", thresholds=[(None, "orange"), (0.8, "green")])  # fmt: skip
    b.stat("اتصال زنده (SSE)", "sum(tsetmc_api_sse_clients)", "پنل‌های باز")
    b.stat("503 پایگاه داده", "sum(increase(tsetmc_api_database_unavailable_total[1h]))",
           "در یک ساعت اخیر", thresholds=[(None, "green"), (1, "red")])  # fmt: skip
    b.series("درخواست‌ها بر اساس مسیر",
             [('sum by (route) (rate(tsetmc_api_requests_total[5m]))', "{{route}}")],
             unit="reqps", w=24)  # fmt: skip
    b.series("تأخیر بر اساس مسیر (صدک ۹۵)", [
        (quantile(0.95, "tsetmc_api_request_duration_seconds", "5m", "route"), "{{route}}")],
        unit="s")  # fmt: skip
    b.series("نتیجه‌ی کش", [
        ('sum by (result) (rate(tsetmc_api_cache_total[5m]))', "{{result}}")],
        "hit: از Redis · shared: منتظر محاسبه‌ی دیگر · not_modified: پاسخ ۳۰۴",
        unit="reqps", stack=True)  # fmt: skip
    return b


def clickhouse() -> Board:
    b = Board(
        "tsetmc-clickhouse", "TSETMCViewer · ClickHouse", "پایگاه داده از endpoint داخلی ClickHouse"
    )
    b.stat("در دسترس", 'max(up{job="clickhouse"}) or vector(0)', thresholds=UP, mappings=YES_NO)
    b.stat("زمان روشن بودن", "max(ClickHouseAsyncMetrics_Uptime)", unit="s")
    b.stat("فضای آزاد دیسک", "min(ClickHouseAsyncMetrics_FilesystemMainPathAvailableBytes"
           " / ClickHouseAsyncMetrics_FilesystemMainPathTotalBytes)", unit="percentunit",
           thresholds=[(None, "red"), (0.1, "orange"), (0.25, "green")])  # fmt: skip
    b.stat("بیشترین part در پارتیشن", "max(ClickHouseAsyncMetrics_MaxPartCountForPartition)",
           thresholds=[(None, "green"), (150, "orange"), (300, "red")])  # fmt: skip
    b.stat("حافظه", "max(ClickHouseMetrics_MemoryTracking)", unit="bytes")
    b.stat("اتصال‌های HTTP", "max(ClickHouseMetrics_HTTPConnection)")
    b.series("کوئری‌ها در ثانیه", [
        ("sum(rate(ClickHouseProfileEvents_SelectQuery[5m]))", "SELECT"),
        ("sum(rate(ClickHouseProfileEvents_InsertQuery[5m]))", "INSERT"),
        ("sum(rate(ClickHouseProfileEvents_FailedQuery[5m]))", "ناموفق"),
    ], unit="reqps")  # fmt: skip
    b.series("ردیف‌های درج‌شده در ثانیه",
             [("sum(rate(ClickHouseProfileEvents_InsertedRows[5m]))", "ردیف")])  # fmt: skip
    b.series("میانگین زمان SELECT", [
        ("sum(rate(ClickHouseProfileEvents_SelectQueryTimeMicroseconds[5m])) "
         "/ sum(rate(ClickHouseProfileEvents_SelectQuery[5m])) / 1e6", "SELECT")],
        unit="s")  # fmt: skip
    b.series("ادغام‌ها و partها", [
        ("max(ClickHouseMetrics_Merge)", "ادغام در حال اجرا"),
        ("max(ClickHouseAsyncMetrics_MaxPartCountForPartition)", "بیشترین part"),
    ])  # fmt: skip
    return b


BOARDS = (overview, collector, api, clickhouse)


def build() -> dict[str, str]:
    return {
        f"{b.uid}.json": json.dumps(b.json(), ensure_ascii=False, indent=2) + "\n"
        for b in (f() for f in BOARDS)
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in build().items():
        (OUT / name).write_text(text, "utf-8")
        print("wrote", OUT / name)
