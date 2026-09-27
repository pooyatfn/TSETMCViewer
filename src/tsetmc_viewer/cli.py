"""Command-line entry point: ``tsetmc-viewer <command>``.

Commands
  migrate               create the database and apply pending schema migrations
  sync-funds            rebuild today's fund universe from TSETMC
  collect               run the per-minute collector loop
  collect-once          run a single collection cycle and exit
  bootstrap             off-hours: catch up daily history + closing snapshot of the last session
  backfill-intraday     rebuild today's minutes missed before the collector started (ADR 0012)
  backfill-sessions     rebuild recent past trading days' minutes from price history (ADR 0013)
  healthcheck           exit 0 if the collector loop is alive (Docker healthcheck)
  alert-relay           forward Alertmanager notifications to Bale / Telegram / a webhook
  replay --date DAY     rebuild clean ticks of DAY from stored raw responses
  quality --date DAY    print the data-quality report of DAY
  backfill --days N     load N trading days of official daily history for equity funds
  api                   serve the HTTP API
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import signal
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from prometheus_client import start_http_server

from tsetmc_viewer import telemetry
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.heartbeat import Heartbeat
from tsetmc_viewer.collector.leadership import Leadership
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import Settings, get_settings
from tsetmc_viewer.logs import configure_logging
from tsetmc_viewer.pipeline.backfill import IntradayBackfill, SessionBackfill
from tsetmc_viewer.pipeline.history import HistorySync
from tsetmc_viewer.pipeline.replay import replay_day
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.clickhouse import create_client, ensure_database
from tsetmc_viewer.storage.migrate import migrate
from tsetmc_viewer.storage.repository import Repository, quality_report
from tsetmc_viewer.storage.tickbus import TickBus

log = logging.getLogger("tsetmc_viewer")


@dataclass
class Services:
    repo: Repository
    tsetmc: TsetmcClient
    clock: MarketClock
    universe: FundUniverse
    sync: UniverseSync
    settings: Settings

    def validator(self) -> Validator:
        return Validator(self.settings.validation, self.clock)


@asynccontextmanager
async def services(settings: Settings) -> AsyncIterator[Services]:
    """Wire the object graph once; every command borrows what it needs."""
    client = await create_client(settings.clickhouse)
    try:
        async with TsetmcClient(settings.tsetmc_base_url, settings.http) as tsetmc:
            repo = Repository(client)
            clock = MarketClock(settings.market)
            sync = UniverseSync(tsetmc, repo, clock)
            yield Services(repo, tsetmc, clock, FundUniverse(sync, repo), sync, settings)
    finally:
        await client.close()


async def _migrate(settings: Settings) -> None:
    await ensure_database(settings.clickhouse)
    client = await create_client(settings.clickhouse)
    try:
        applied = await migrate(client, cluster=settings.clickhouse.cluster)
    finally:
        await client.close()
    log.info("migrations done", extra={"applied": applied})


async def _sync_funds(settings: Settings) -> None:
    async with services(settings) as s:
        refs = await s.sync.sync()
    for ref in sorted(refs, key=lambda r: (r.fund_type, r.symbol)):
        print(f"{ref.fund_type.label_fa:<10} {ref.symbol:<14} {ref.ins_code}")


async def _collect(
    settings: Settings, *, mode: str, through: date | None = None, days: int | None = None
) -> None:
    bus = TickBus.from_url(settings.redis_url)
    async with services(settings) as s:
        collector = Collector(
            s.tsetmc,
            s.repo,
            s.clock,
            s.universe,
            s.validator(),
            history=HistorySync(s.tsetmc, s.repo, s.clock),
            history_max_days=settings.history_max_days,
            bus=bus,
            heartbeat=Heartbeat(Path(settings.collector_heartbeat_path)),
            leadership=(
                Leadership(
                    bus,
                    ttl_seconds=settings.collector_leader_lease_seconds,
                    renew_every=settings.collector_leader_lease_seconds / 4,
                )
                if bus.enabled and settings.collector_leader_lease_seconds and mode == "loop"
                else None
            ),
            alert_after_failures=settings.collector_alert_after_failures,
            backfill=(
                IntradayBackfill(s.tsetmc, s.repo, s.clock)
                if settings.intraday_backfill or mode == "backfill-intraday"
                else None
            ),
            session_backfill=(
                SessionBackfill(s.tsetmc, s.repo, s.clock)
                if settings.session_backfill_days or mode == "backfill-sessions"
                else None
            ),
            session_backfill_days=days if days is not None else settings.session_backfill_days,
        )
        try:
            match mode:
                case "once":
                    await collector.collect_once()
                case "backfill-intraday":
                    report = await collector.backfill_intraday(s.clock.now().date())
                    print(report or "nothing to do (or failed: see the log)")
                case "backfill-sessions":
                    reports = await collector.backfill_sessions(through or s.clock.now().date())
                    for rep in reports:
                        print(rep)
                case "bootstrap":
                    r = await collector.bootstrap()
                    snap = r.snapshot.status if r.snapshot else "not needed"
                    print(f"session {r.session}: history {r.history_days} days, snapshot {snap}")
                case _:
                    if settings.collector_metrics_port:
                        start_http_server(settings.collector_metrics_port)
                    await collector.run_forever(
                        settings.collect_interval_seconds,
                        ignore_market_hours=settings.collect_ignore_market_hours,
                        bootstrap=settings.collect_bootstrap,
                        stop=_stop_on_signals(),
                    )
        finally:
            await bus.close()


def _stop_on_signals() -> asyncio.Event:
    """SIGTERM (docker stop) / SIGINT set an event: the current cycle finishes, then exit."""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(sig: signal.Signals) -> None:
        log.info("stop requested", extra={"signal": sig.name})
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, request_stop, sig)
    return stop


def _healthcheck(settings: Settings) -> int:
    ok, reason = Heartbeat(Path(settings.collector_heartbeat_path)).check(
        MarketClock(settings.market).now()
    )
    print(("healthy: " if ok else "unhealthy: ") + reason)
    return 0 if ok else 1


async def _replay(settings: Settings, day: date) -> None:
    async with services(settings) as s:
        report = await replay_day(s.repo, day, s.clock.now(), s.validator())
    print(f"replayed {report.runs} cycles → {report.ticks} ticks, {report.issues} issues")


async def _backfill(settings: Settings, days: int) -> None:
    async with services(settings) as s:
        funds = await s.universe.get(s.clock.now().date())
        report = await HistorySync(s.tsetmc, s.repo, s.clock).sync(funds.values(), days=days)
    print(f"{report.rows} daily rows for {report.funds} funds; failed: {report.failed or 'none'}")


async def _quality(settings: Settings, day: date) -> None:
    client = await create_client(settings.clickhouse)
    try:
        r = await quality_report(client, day)
    finally:
        await client.close()
    print(f"Data quality — {day}")
    print(f"  cycles:        {sum(r.runs_by_status.values())}  {r.runs_by_status}")
    print(f"  completeness:  {r.completeness:.2%} of expected fund-minutes")
    print(f"  ticks:         {r.ticks}")
    for name, n in sorted(r.flag_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {name:<24} {n:>7}  {n / r.ticks:6.1%}" if r.ticks else f"    {name}")
    print("  issues:")
    for check, severity, action, n in r.issues:
        print(f"    {severity:<6} {check:<24} {action:<24} {n:>6}")


def _serve_api(settings: Settings, host: str, port: int, workers: int) -> None:
    import uvicorn

    if workers <= 1:
        from tsetmc_viewer.api.app import create_app

        uvicorn.run(create_app(settings), host=host, port=port, log_config=None)
        return
    # Several processes: metrics must be aggregated across them (telemetry.py), so every
    # worker writes to a shared directory that is wiped on start. Set before workers spawn.
    metrics_dir = Path(os.environ.setdefault(telemetry.MULTIPROC_ENV, "/tmp/tsetmc-api-metrics"))
    shutil.rmtree(metrics_dir, ignore_errors=True)
    metrics_dir.mkdir(parents=True)
    uvicorn.run(
        "tsetmc_viewer.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=workers,
        log_config=None,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tsetmc-viewer")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("sync-funds")
    sub.add_parser("collect")
    sub.add_parser("collect-once")
    sub.add_parser("bootstrap")
    sub.add_parser("backfill-intraday")
    sessions = sub.add_parser("backfill-sessions")
    sessions.add_argument("--through", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    sessions.add_argument("--days", type=int, default=None, help="default: SESSION_BACKFILL_DAYS")
    sub.add_parser("healthcheck")
    relay = sub.add_parser("alert-relay")
    relay.add_argument("--host", default="0.0.0.0")
    relay.add_argument("--port", type=int, default=9095)
    replay = sub.add_parser("replay")
    replay.add_argument("--date", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--days", type=int, default=None, help="default: HISTORY_MAX_DAYS")
    quality = sub.add_parser("quality")
    quality.add_argument("--date", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    api = sub.add_parser("api")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--workers", type=int, default=None, help="default: API_WORKERS")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    match args.command:
        case "migrate":
            asyncio.run(_migrate(settings))
        case "sync-funds":
            asyncio.run(_sync_funds(settings))
        case "collect":
            asyncio.run(_collect(settings, mode="loop"))
        case "collect-once":
            asyncio.run(_collect(settings, mode="once"))
        case "bootstrap":
            asyncio.run(_collect(settings, mode="bootstrap"))
        case "backfill-intraday":
            asyncio.run(_collect(settings, mode="backfill-intraday"))
        case "backfill-sessions":
            asyncio.run(
                _collect(settings, mode="backfill-sessions", through=args.through, days=args.days)
            )
        case "healthcheck":
            sys.exit(_healthcheck(settings))
        case "alert-relay":
            import uvicorn

            from tsetmc_viewer.alerting.relay import create_relay_app

            app = create_relay_app(settings.alerts)
            uvicorn.run(app, host=args.host, port=args.port, log_config=None)
        case "replay":
            asyncio.run(_replay(settings, args.date))
        case "backfill":
            asyncio.run(_backfill(settings, args.days or settings.history_max_days))
        case "quality":
            asyncio.run(_quality(settings, args.date))
        case "api":
            _serve_api(settings, args.host, args.port, args.workers or settings.api_workers)


if __name__ == "__main__":
    main()
