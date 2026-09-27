"""Loop-level behaviour of the collector: graceful stop, failure alerting, heartbeat."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import respx

from support import BASE, TEHRAN, MemoryStore, mock_tsetmc
from tsetmc_viewer.cli import main
from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.collector.heartbeat import Heartbeat
from tsetmc_viewer.collector.service import Collector
from tsetmc_viewer.config import HttpSettings, MarketSettings, ValidationSettings, get_settings
from tsetmc_viewer.pipeline.universe import FundUniverse, UniverseSync
from tsetmc_viewer.pipeline.validate import Validator
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.storage.repository import CollectionRun

NOW = datetime(2026, 9, 26, 10, 0, 30, tzinfo=TEHRAN)  # Saturday, market open


class FixedClock(MarketClock):
    def now(self) -> datetime:
        return NOW


def make(
    client: TsetmcClient,
    store: MemoryStore,
    heartbeat: Heartbeat | None = None,
    cls: type[Collector] = Collector,
) -> Collector:
    clock = FixedClock(MarketSettings())
    universe = FundUniverse(UniverseSync(client, store, clock), store)
    return cls(
        client,
        store,
        clock,
        universe,
        Validator(ValidationSettings(), clock),
        heartbeat=heartbeat,
    )


async def test_stop_cuts_the_sleep_short(http_settings: HttpSettings, tmp_path: Path) -> None:
    store = MemoryStore()
    beat = Heartbeat(tmp_path / "hb.json")
    stop = asyncio.Event()
    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            collector = make(client, store, beat)
            asyncio.get_running_loop().call_later(0.3, stop.set)
            started = time.monotonic()
            await collector.run_forever(60, ignore_market_hours=True, bootstrap=False, stop=stop)
    assert time.monotonic() - started < 5  # not the 29.5 s left until the next minute
    assert len(store.runs) == 1
    assert beat.check(NOW)[0]


async def test_stop_during_a_cycle_lets_it_finish(http_settings: HttpSettings) -> None:
    store = MemoryStore()
    stop = asyncio.Event()

    class Interrupted(Collector):
        async def collect_once(self, tick: datetime | None = None) -> CollectionRun:
            stop.set()  # "docker stop" arrives mid-cycle
            await asyncio.sleep(0.05)
            return await super().collect_once(tick)

    with respx.mock as router:
        mock_tsetmc(router)
        async with TsetmcClient(BASE, http_settings) as client:
            base = make(client, store)
            collector = Interrupted(client, store, base._clock, base._universe, base._validator)
            await collector.run_forever(60, ignore_market_hours=True, bootstrap=False, stop=stop)
    assert [r.status for r in store.runs] == ["ok"]  # written completely, then stopped
    assert store.ticks


def test_failures_alert_once_and_recovery_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    collector = Collector(None, None, None, None, None, alert_after_failures=3)  # type: ignore[arg-type]
    with caplog.at_level(logging.INFO, logger="tsetmc_viewer.collector.service"):
        for _ in range(5):
            collector._record(False)
        collector._record(True)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1  # edge-triggered: not one per failed minute
    assert errors[0].failed_cycles == 3  # type: ignore[attr-defined]
    assert any(r.getMessage() == "collector recovered" for r in caplog.records)
    assert collector.failed_streak == 0


def test_heartbeat_deadline(tmp_path: Path) -> None:
    beat = Heartbeat(tmp_path / "hb.json")
    assert beat.check(NOW) == (False, "no heartbeat yet")
    beat.write({"state": "sleeping", "deadline": (NOW + timedelta(minutes=5)).isoformat()})
    assert beat.check(NOW)[0]
    healthy, reason = beat.check(NOW + timedelta(minutes=6))
    assert not healthy
    assert "missed deadline" in reason


def test_healthcheck_command_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "hb.json"
    monkeypatch.setenv("COLLECTOR_HEARTBEAT_PATH", str(path))
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as missing:
            main(["healthcheck"])
        assert missing.value.code == 1
        far = datetime.now(TEHRAN) + timedelta(hours=1)
        Heartbeat(path).write({"state": "collecting", "deadline": far.isoformat()})
        with pytest.raises(SystemExit) as ok:
            main(["healthcheck"])
        assert ok.value.code == 0
        assert "healthy: collecting" in capsys.readouterr().out
    finally:
        get_settings.cache_clear()
