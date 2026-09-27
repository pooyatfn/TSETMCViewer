"""Application settings, loaded from environment variables (and ``.env``)."""

from __future__ import annotations

from datetime import date, time
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClickHouseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLICKHOUSE_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: SecretStr = SecretStr("")
    database: str = "tsetmc"
    # Empty (default): plain MergeTree/ReplacingMergeTree/AggregatingMergeTree, one node.
    # Set (e.g. "tsetmc_cluster"): migrate() runs every statement `ON CLUSTER` and
    # rewrites those engines to their Replicated* form (ADR 0011). Needs a working
    # Keeper/ZooKeeper and a matching <remote_servers> cluster of that name.
    cluster: str = ""


class HttpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HTTP_", env_file=".env", extra="ignore")

    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    max_concurrency: int = 8


class MarketSettings(BaseSettings):
    """Trading calendar. Iranian equity market: Saturday–Wednesday, 09:00–12:30 Tehran."""

    model_config = SettingsConfigDict(env_prefix="MARKET_", env_file=".env", extra="ignore")

    timezone: str = "Asia/Tehran"
    open_time: time = time(9, 0)
    close_time: time = time(12, 30)
    # Python weekday numbers: Monday=0 ... Saturday=5, Sunday=6.
    trading_weekdays: frozenset[int] = frozenset({5, 6, 0, 1, 2})
    # Official holidays (domain/calendar.py) close the market; false = weekdays only.
    holidays: bool = True
    # One-off closures announced by the exchange, as JSON: {"2026-10-05": "reason"}.
    extra_holidays: dict[date, str] = Field(default_factory=dict)
    # Minutes after the open to wait for the first trade before calling the day closed.
    session_guard_minutes: int = 20


class ValidationSettings(BaseSettings):
    """Thresholds for the per-cycle data-quality checks (docs/04-data-quality.md)."""

    model_config = SettingsConfigDict(env_prefix="VALIDATION_", env_file=".env", extra="ignore")

    nav_stale_minutes: int = 20
    nav_jump_ratio: float = 0.10  # |NAV change| between ticks above this is suspicious
    client_mismatch_ratio: float = 0.02  # tolerance for Σ buy volumes vs traded volume
    max_gap_fill_minutes: int = 30
    feed_stale_cycles: int = 3


class AlertSettings(BaseSettings):
    """Where the alert relay delivers Alertmanager notifications (all optional)."""

    model_config = SettingsConfigDict(env_prefix="ALERT_", env_file=".env", extra="ignore")

    # Bale (بله) bot: Telegram-compatible API, reachable inside Iran.
    bale_token: SecretStr = SecretStr("")
    bale_chat_id: str = ""
    bale_api: str = "https://tapi.bale.ai"
    telegram_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    telegram_api: str = "https://api.telegram.org"
    # Any HTTP endpoint (Slack/Mattermost bridge, n8n, ...): receives Alertmanager's JSON.
    webhook_url: str = ""
    # Base URL of the docs site, to turn runbook anchors into links.
    docs_url: str = "http://localhost:8001"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    log_json: bool = False

    tsetmc_base_url: str = "https://cdn.tsetmc.com/api"

    # Redis for the response cache and tick events; empty disables both (ADR 0006).
    redis_url: str = "redis://localhost:6379/0"
    # Comma-separated origins allowed to call the API from a browser (web panel dev server).
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # API worker processes (uvicorn); >1 switches metrics to multiprocess mode.
    api_workers: int = 1

    collect_interval_seconds: int = 60
    # Collect outside market hours too (useful for development and demos).
    collect_ignore_market_hours: bool = False
    # On start outside market hours: catch up daily history and, if the last session has
    # no minute data, store its closing snapshot — so a fresh install is not empty.
    collect_bootstrap: bool = True
    # Started late? Rebuild today's missed minutes (price, volume, value, trade count)
    # from TSETMC's trade list, once a day, after checking it against live ticks (ADR 0012).
    intraday_backfill: bool = True
    # At boot (outside market hours): rebuild this many recent trading days of minute
    # data the collector never ran during, from TSETMC's price-history feed, checked
    # against the official daily rollup (ADR 0013). 0 disables it.
    session_backfill_days: int = 5
    # Window of official daily history loaded into an empty database (trading days).
    history_max_days: int = 400
    # Liveness file of the collector loop, read by `tsetmc-viewer healthcheck` (Docker).
    collector_heartbeat_path: str = "/tmp/tsetmc-collector-heartbeat.json"
    # Prometheus metrics of the collector on this port (0 = off); the API serves /metrics.
    collector_metrics_port: int = 9108
    # Leader lease for collector replicas, in seconds (0 = no election; needs Redis).
    collector_leader_lease_seconds: int = 60
    # Consecutive failed cycles before one ERROR is logged (edge-triggered).
    collector_alert_after_failures: int = 3

    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    http: HttpSettings = Field(default_factory=HttpSettings)
    market: MarketSettings = Field(default_factory=MarketSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
