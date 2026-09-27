"""Rebuild clean ticks for a past day from ``raw_snapshots`` (ADR 0003).

Use after fixing a parser or a transformation: the stored raw responses are
fed through exactly the same ``process_cycle`` as the live collector. Because
``fund_ticks`` is a ReplacingMergeTree keyed on (ins_code, ts), re-inserting
replaces the old rows instead of duplicating them.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.pipeline.cycle import process_cycle
from tsetmc_viewer.pipeline.transform import FundTick, MarketTick
from tsetmc_viewer.pipeline.validate import QualityIssue, Validator
from tsetmc_viewer.storage.repository import RawRun

log = logging.getLogger(__name__)


class ReplayStore(Protocol):
    async def load_raw_runs(self, day: date) -> list[RawRun]: ...
    async def load_funds(self, synced_on: date | None = None) -> list[FundRef]: ...
    async def insert_fund_ticks(self, ticks: Sequence[FundTick]) -> int: ...
    async def insert_market_tick(self, tick: MarketTick) -> None: ...
    async def insert_quality_issues(self, issues: Sequence[QualityIssue]) -> int: ...
    async def delete_quality_issues(self, day: date) -> None: ...


@dataclass(frozen=True, slots=True)
class ReplayReport:
    runs: int
    ticks: int
    issues: int


async def replay_day(
    store: ReplayStore, day: date, now: datetime, validator: Validator
) -> ReplayReport:
    """Re-run parse → transform → validate for every stored cycle of ``day``, in order."""
    funds = await store.load_funds(synced_on=day) or await store.load_funds()
    universe = {f.ins_code: f for f in funds if f.fund_type.is_equity}
    written = issues = 0
    runs = await store.load_raw_runs(day)
    await store.delete_quality_issues(day)
    for run in runs:
        result = process_cycle(
            responses=run.responses,
            universe=universe,
            ts=run.tick,
            run_id=run.run_id,
            ingested_at=now,
        )
        checked = validator.validate(result.batch, ts=run.tick, run_id=run.run_id, ingested_at=now)
        written += await store.insert_fund_ticks(checked.ticks)
        issues += await store.insert_quality_issues(checked.issues)
        if result.market is not None:
            await store.insert_market_tick(result.market)
    log.info(
        "replay finished",
        extra={"day": str(day), "runs": len(runs), "ticks": written, "issues": issues},
    )
    return ReplayReport(len(runs), written, issues)
