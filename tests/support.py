"""Test helpers: recorded TSETMC fixtures, a fake TSETMC server and in-memory storage."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
import respx

from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.domain.status import FundState
from tsetmc_viewer.pipeline.backfill import BackfillLog, BackfillTick
from tsetmc_viewer.pipeline.history import HistoryRow
from tsetmc_viewer.pipeline.transform import FundTick, MarketTick
from tsetmc_viewer.pipeline.universe import FundRecord
from tsetmc_viewer.pipeline.validate import QualityIssue
from tsetmc_viewer.sources.http import RawResponse
from tsetmc_viewer.storage.repository import CollectionRun, RawRun

SAMPLE = Path(__file__).parent / "fixtures" / "sample"
BASE = "https://cdn.tsetmc.com/api"
TEHRAN = ZoneInfo("Asia/Tehran")

# Instrument codes of the recorded sample funds.
ATLAS = "11427939669935844"  # اطلس — equity (IFB)
AGAS = "33887145736684266"  # آگاس — equity (IFB)
AHROM = "17914401175772326"  # اهرم — leveraged equity
DARA1 = "62235397452612911"  # دارا یکم — equity (TSE)
YAGHUT = "1438514795814416"  # یاقوت — fixed income (must be excluded)
CHATR = "118005828419984"  # چتر — sector (insurance)
AKAM = "490987973229371"  # آکام — fixed income
GARANTI = "971068957336171"  # گارانتی — mixed
EQUITY_SAMPLES = {ATLAS, AGAS, AHROM, DARA1, CHATR}


def fixture(name: str) -> Any:
    return json.loads((SAMPLE / name).read_text("utf-8"))


def _file_or_404(prefix: str) -> Any:
    def handler(request: httpx.Request, ins: str) -> httpx.Response:
        path = SAMPLE / f"{prefix}_{ins}.json"
        if path.exists():
            return httpx.Response(200, content=path.read_bytes())
        return httpx.Response(404)

    return handler


def mock_tsetmc(router: respx.MockRouter, *, market_watch: Any = None) -> None:
    """Serve the recorded sample responses on the TSETMC URLs."""
    router.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(
        return_value=httpx.Response(200, json=market_watch or fixture("market_watch.json"))
    )
    router.get(f"{BASE}/ClientType/GetClientTypeAll").mock(
        return_value=httpx.Response(200, json=fixture("client_type_all.json"))
    )
    router.get(f"{BASE}/MarketData/GetMarketOverview/1").mock(
        return_value=httpx.Response(200, json=fixture("market_overview.json"))
    )
    router.get(url__regex=re.escape(BASE) + r"/Fund/GetETFByInsCode/(?P<ins>\d+)$").mock(
        side_effect=_file_or_404("etf")
    )
    # Trading status: the recorded answer ("A", مجاز) stands in for every instrument.
    router.get(url__regex=re.escape(BASE) + r"/ClosingPrice/GetClosingPriceInfo/\d+$").mock(
        return_value=httpx.Response(200, json=fixture("closing_price_info_11427939669935844.json"))
    )
    router.get(url__regex=re.escape(BASE) + r"/Instrument/GetInstrumentInfo/(?P<ins>\d+)$").mock(
        side_effect=_file_or_404("instrument_info")
    )
    router.get(
        url__regex=re.escape(BASE) + r"/ClosingPrice/GetClosingPriceDailyList/(?P<ins>\d+)/0$"
    ).mock(side_effect=_file_or_404("daily_history"))
    router.get(url__regex=re.escape(BASE) + r"/ClientType/GetClientTypeHistory/(?P<ins>\d+)$").mock(
        side_effect=_file_or_404("client_history")
    )


@dataclass
class MemoryStore:
    """In-memory stand-in for ``Repository`` (satisfies every storage Protocol)."""

    raw: list[RawResponse] = field(default_factory=list)
    runs: list[CollectionRun] = field(default_factory=list)
    ticks: list[FundTick] = field(default_factory=list)
    market: list[MarketTick] = field(default_factory=list)
    funds: dict[str, tuple[FundRecord, datetime]] = field(default_factory=dict)
    units: dict[tuple[date, str], int] = field(default_factory=dict)
    issues: list[QualityIssue] = field(default_factory=list)
    history: list[HistoryRow] = field(default_factory=list)
    market_days: dict[date, tuple[bool, str]] = field(default_factory=dict)
    backfill: list[BackfillTick] = field(default_factory=list)
    backfill_log: list[BackfillLog] = field(default_factory=list)
    states: list[FundState] = field(default_factory=list)

    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int:
        self.raw.extend(responses)
        return len(responses)

    async def insert_run(self, run: CollectionRun) -> None:
        self.runs.append(run)

    async def insert_fund_ticks(self, ticks: Sequence[FundTick]) -> int:
        self.ticks.extend(ticks)
        return len(ticks)

    async def insert_market_tick(self, tick: MarketTick) -> None:
        self.market.append(tick)

    async def upsert_funds(self, records: Sequence[FundRecord], at: datetime) -> None:
        for r in records:
            self.funds[r.ref.ins_code] = (r, at)

    async def insert_fund_units(self, day: date, units: Mapping[str, int], at: datetime) -> None:
        for ins, n in units.items():
            self.units[(day, ins)] = n

    async def load_funds(self, synced_on: date | None = None) -> list[FundRef]:
        return [
            rec.ref
            for rec, at in self.funds.values()
            if rec.is_active and (synced_on is None or at.date() == synced_on)
        ]

    async def load_raw_runs(self, day: date) -> list[RawRun]:
        return []

    async def insert_history(self, rows: Sequence[HistoryRow]) -> int:
        self.history.extend(rows)
        return len(rows)

    async def record_market_day(self, day: date, *, trading: bool, note: str, at: datetime) -> None:
        self.market_days[day] = (trading, note)

    async def load_market_days(self) -> list[tuple[date, bool, str]]:
        return [(d, t, n) for d, (t, n) in self.market_days.items()]

    async def latest_history_date(self) -> date | None:
        return max((r.trade_date for r in self.history), default=None)

    async def insert_quality_issues(self, issues: Sequence[QualityIssue]) -> int:
        self.issues.extend(issues)
        return len(issues)

    async def delete_quality_issues(self, day: date) -> None:
        self.issues = [i for i in self.issues if i.ts.date() != day]

    async def insert_fund_states(self, states: Sequence[FundState]) -> int:
        self.states.extend(states)
        return len(states)

    async def load_live_volumes(self, day: date) -> dict[str, list[tuple[datetime, int]]]:
        out: dict[str, list[tuple[datetime, int]]] = {}
        for t in sorted(self.ticks, key=lambda t: t.ts):
            if t.ts.date() == day and not t.quality_flags & QualityFlag.FORWARD_FILLED:
                out.setdefault(t.ins_code, []).append((t.ts, t.volume))
        return out

    async def backfilled_funds(self, day: date) -> set[str]:
        return {r.ins_code for r in self.backfill_log if r.day == day and r.status != "error"}

    async def insert_backfill(self, ticks: Sequence[BackfillTick]) -> int:
        self.backfill.extend(ticks)
        return len(ticks)

    async def insert_backfill_log(self, rows: Sequence[BackfillLog]) -> int:
        self.backfill_log.extend(rows)
        return len(rows)

    async def load_last_ticks(self, day: date) -> list[FundTick]:
        last: dict[str, FundTick] = {}
        for t in self.ticks:
            if t.ts.date() == day and (t.ins_code not in last or t.ts >= last[t.ins_code].ts):
                last[t.ins_code] = t
        return list(last.values())
