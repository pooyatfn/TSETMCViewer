"""ClickHouse persistence for the pipeline. Inserts are batched per cycle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from clickhouse_connect.driver.asyncclient import AsyncClient

from tsetmc_viewer.domain.funds import FundRef, FundType
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.domain.status import FundState
from tsetmc_viewer.pipeline.transform import FundTick
from tsetmc_viewer.sources.http import RawResponse

if TYPE_CHECKING:
    from tsetmc_viewer.pipeline.backfill import BackfillLog, BackfillTick
    from tsetmc_viewer.pipeline.history import HistoryRow
    from tsetmc_viewer.pipeline.transform import MarketTick
    from tsetmc_viewer.pipeline.universe import FundRecord
    from tsetmc_viewer.pipeline.validate import QualityIssue

RunStatus = Literal["ok", "partial", "failed"]

_RAW_COLUMNS = [
    "fetched_at",
    "run_id",
    "source",
    "endpoint",
    "ins_code",
    "status_code",
    "latency_ms",
    "attempts",
    "payload",
]
_RUN_COLUMNS = [
    "run_id",
    "started_at",
    "finished_at",
    "tick",
    "status",
    "requests",
    "failed",
    "expected_funds",
    "received_funds",
    "issues",
    "filled",
    "repaired",
    "note",
]
_FUND_COLUMNS = [
    "ins_code",
    "symbol",
    "name",
    "isin",
    "fund_type",
    "market",
    "board",
    "manager",
    "custodian",
    "is_active",
    "source",
    "updated_at",
]


@dataclass(frozen=True, slots=True)
class CollectionRun:
    run_id: UUID
    started_at: datetime
    finished_at: datetime
    tick: datetime
    status: RunStatus
    requests: int
    failed: int
    expected_funds: int = 0
    received_funds: int = 0
    issues: int = 0
    filled: int = 0
    repaired: int = 0
    note: str = ""


@dataclass(slots=True)
class RawRun:
    """Everything one past cycle fetched, for replay."""

    run_id: UUID
    tick: datetime
    responses: list[RawResponse] = field(default_factory=list)


class Repository:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    # --- raw + runs -------------------------------------------------------------
    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int:
        if not responses:
            return 0
        rows = [
            [
                r.fetched_at,
                run_id,
                r.source,
                r.endpoint,
                r.ins_code,
                r.status_code,
                r.latency_ms,
                r.attempts,
                r.payload.decode("utf-8", errors="replace"),
            ]
            for r in responses
        ]
        await self._client.insert("raw_snapshots", rows, column_names=_RAW_COLUMNS)
        return len(rows)

    async def insert_run(self, run: CollectionRun) -> None:
        row = [getattr(run, c) for c in _RUN_COLUMNS]
        await self._client.insert("collection_runs", [row], column_names=_RUN_COLUMNS)

    async def load_raw_runs(self, day: date) -> list[RawRun]:
        """Raw responses of every collection cycle on ``day``, grouped by run."""
        result = await self._client.query(
            """
            SELECT r.run_id, c.tick, r.fetched_at, r.source, r.endpoint, r.ins_code,
                   r.status_code, r.latency_ms, r.attempts, r.payload
            FROM raw_snapshots AS r
            INNER JOIN (SELECT run_id, tick FROM collection_runs WHERE toDate(tick) = {day:Date})
                AS c ON c.run_id = r.run_id
            ORDER BY c.tick, r.endpoint
            """,
            parameters={"day": day},
        )
        runs: dict[UUID, RawRun] = {}
        for (
            run_id,
            tick,
            fetched,
            source,
            endpoint,
            ins,
            status,
            latency,
            attempts,
            payload,
        ) in result.result_rows:
            run = runs.setdefault(run_id, RawRun(run_id, tick))
            run.responses.append(
                RawResponse(
                    source=source,
                    endpoint=endpoint,
                    url="",
                    status_code=status,
                    payload=payload.encode("utf-8") if isinstance(payload, str) else payload,
                    fetched_at=fetched,
                    latency_ms=latency,
                    ins_code=ins,
                    attempts=attempts,
                )
            )
        return list(runs.values())

    # --- ticks --------------------------------------------------------------------
    async def insert_fund_ticks(self, ticks: Sequence[FundTick]) -> int:
        if not ticks:
            return 0
        await self._client.insert(
            "fund_ticks", [t.as_row() for t in ticks], column_names=ticks[0].columns()
        )
        return len(ticks)

    async def insert_market_tick(self, tick: MarketTick) -> None:
        await self._client.insert("market_ticks", [tick.as_row()], column_names=tick.columns())

    async def load_last_ticks(self, day: date) -> list[FundTick]:
        """Latest tick of each fund on ``day`` (warms the validator after a restart)."""
        cols = FundTick.columns()
        result = await self._client.query(
            f"SELECT {', '.join(cols)} FROM fund_ticks FINAL "
            "WHERE toDate(ts) = {day:Date} ORDER BY ts DESC LIMIT 1 BY ins_code",
            parameters={"day": day},
        )
        return [FundTick(**dict(zip(cols, row, strict=True))) for row in result.result_rows]

    # --- fund trading status ---------------------------------------------------------------
    async def insert_fund_states(self, states: Sequence[FundState]) -> int:
        if not states:
            return 0
        await self._client.insert(
            "fund_state", [s.as_row() for s in states], column_names=states[0].columns()
        )
        return len(states)

    # --- intraday backfill (ADR 0012) --------------------------------------------------
    async def load_live_volumes(self, day: date) -> dict[str, list[tuple[datetime, int]]]:
        """Collected (not forward-filled) volume of every fund at every tick of ``day``."""
        result = await self._client.query(
            "SELECT ins_code, ts, volume FROM fund_ticks FINAL "
            "WHERE toDate(ts) = {day:Date} AND bitAnd(quality_flags, {ff:UInt32}) = 0 "
            "ORDER BY ins_code, ts",
            parameters={"day": day, "ff": int(QualityFlag.FORWARD_FILLED)},
        )
        out: dict[str, list[tuple[datetime, int]]] = {}
        for ins, ts, volume in result.result_rows:
            out.setdefault(ins, []).append((ts, int(volume)))
        return out

    async def backfilled_funds(self, day: date) -> set[str]:
        """Funds already decided for ``day``; errors are left out so they are retried."""
        result = await self._client.query(
            "SELECT ins_code FROM intraday_backfill_log FINAL "
            "WHERE day = {day:Date} AND status != 'error'",
            parameters={"day": day},
        )
        return {row[0] for row in result.result_rows}

    async def insert_backfill(self, ticks: Sequence[BackfillTick]) -> int:
        if not ticks:
            return 0
        await self._client.insert(
            "fund_ticks_backfill", [t.as_row() for t in ticks], column_names=ticks[0].columns()
        )
        return len(ticks)

    async def insert_backfill_log(self, rows: Sequence[BackfillLog]) -> int:
        if not rows:
            return 0
        await self._client.insert(
            "intraday_backfill_log", [r.as_row() for r in rows], column_names=rows[0].columns()
        )
        return len(rows)

    async def load_history_day(self, day: date) -> dict[str, tuple[int, int, int]]:
        """Official (volume, value, trade_count) of every fund on ``day``.

        The trust check for ``SessionBackfill``: a past day has no live ticks to
        compare against, so the reconstructed series is checked against TSETMC's own
        official daily rollup instead.
        """
        result = await self._client.query(
            "SELECT ins_code, volume, value, trade_count FROM fund_history_daily FINAL "
            "WHERE trade_date = {day:Date}",
            parameters={"day": day},
        )
        return {ins: (int(v), int(val), int(tc)) for ins, v, val, tc in result.result_rows}

    # --- trading calendar observations -------------------------------------------------
    async def record_market_day(self, day: date, *, trading: bool, note: str, at: datetime) -> None:
        await self._client.insert(
            "market_calendar",
            [[day, int(trading), note, at]],
            column_names=["day", "trading", "note", "recorded_at"],
        )

    async def load_market_days(self) -> list[tuple[date, bool, str]]:
        result = await self._client.query("SELECT day, trading, note FROM market_calendar FINAL")
        return [(d, bool(t), n) for d, t, n in result.result_rows]

    # --- history ---------------------------------------------------------------------
    async def latest_history_date(self) -> date | None:
        result = await self._client.query("SELECT max(trade_date) FROM fund_history_daily")
        d = result.result_rows[0][0] if result.result_rows else None
        return d if isinstance(d, date) and d.year > 1970 else None

    async def insert_history(self, rows: Sequence[HistoryRow], chunk: int = 20_000) -> int:
        for i in range(0, len(rows), chunk):
            part = rows[i : i + chunk]
            await self._client.insert(
                "fund_history_daily", [r.as_row() for r in part], column_names=part[0].columns()
            )
        return len(rows)

    # --- data quality ---------------------------------------------------------------
    async def insert_quality_issues(self, issues: Sequence[QualityIssue]) -> int:
        if not issues:
            return 0
        await self._client.insert(
            "data_quality_log", [i.as_row() for i in issues], column_names=issues[0].columns()
        )
        return len(issues)

    async def delete_quality_issues(self, day: date) -> None:
        """Used by replay so re-validated days do not accumulate duplicate log rows."""
        await self._client.command(
            "ALTER TABLE data_quality_log DELETE WHERE toDate(ts) = {day:Date}",
            parameters={"day": day},
            settings={"mutations_sync": 1},
        )

    # --- reference data -----------------------------------------------------------
    async def upsert_funds(self, records: Sequence[FundRecord], at: datetime) -> None:
        if not records:
            return
        rows = [
            [
                r.ref.ins_code,
                r.ref.symbol,
                r.ref.name,
                r.ref.isin,
                r.ref.fund_type.value,
                r.market,
                r.board,
                "",
                "",
                int(r.is_active),
                "tsetmc",
                at,
            ]
            for r in records
        ]
        await self._client.insert("funds", rows, column_names=_FUND_COLUMNS)

    async def insert_fund_units(self, day: date, units: Mapping[str, int], at: datetime) -> None:
        if not units:
            return
        rows = [[day, ins, n, at] for ins, n in units.items()]
        await self._client.insert(
            "fund_daily", rows, column_names=["trade_date", "ins_code", "units", "updated_at"]
        )

    async def load_funds(self, synced_on: date | None = None) -> list[FundRef]:
        """Active funds (latest version), optionally only if synced on ``synced_on``."""
        result = await self._client.query(
            """
            SELECT f.ins_code, f.symbol, f.name, f.isin, f.fund_type, u.units
            FROM (SELECT * FROM funds FINAL) AS f
            LEFT JOIN (
                SELECT ins_code, argMax(units, trade_date) AS units
                FROM fund_daily FINAL GROUP BY ins_code
            ) AS u ON u.ins_code = f.ins_code
            WHERE f.is_active = 1
              AND ({day:Nullable(Date)} IS NULL OR toDate(f.updated_at) = {day:Nullable(Date)})
            ORDER BY f.symbol
            """,
            parameters={"day": synced_on},
        )
        return [
            FundRef(
                ins_code=ins,
                symbol=symbol,
                name=name,
                isin=isin,
                fund_type=FundType(fund_type),
                units=int(units) if units else None,
            )
            for ins, symbol, name, isin, fund_type, units in result.result_rows
        ]


@dataclass(frozen=True, slots=True)
class QualityReport:
    runs_by_status: dict[str, int]
    completeness: float  # Σ received / Σ expected funds over the day's cycles
    ticks: int
    flag_counts: dict[str, int]  # QualityFlag name → ticks carrying it
    issues: list[tuple[str, str, str, int]]  # (check, severity, action, count)


async def quality_report(client: AsyncClient, day: date) -> QualityReport:
    """Daily data-quality summary; the SQL mirrors docs/04-data-quality.md."""
    from tsetmc_viewer.domain.quality import QualityFlag

    params = {"day": day}
    runs = await client.query(
        "SELECT status, count(), sum(received_funds), sum(expected_funds) FROM collection_runs "
        "WHERE toDate(tick) = {day:Date} GROUP BY status",
        parameters=params,
    )
    by_status = {str(r[0]): int(r[1]) for r in runs.result_rows}
    received = sum(int(r[2]) for r in runs.result_rows)
    expected = sum(int(r[3]) for r in runs.result_rows)

    flags = [f for f in QualityFlag if f]
    sums = ", ".join(f"countIf(bitAnd(quality_flags, {int(f)}) != 0)" for f in flags)
    ticks = await client.query(
        f"SELECT count(), {sums} FROM fund_ticks FINAL WHERE toDate(ts) = {{day:Date}}",
        parameters=params,
    )
    row = ticks.result_rows[0]
    flag_counts = {str(f.name): int(n) for f, n in zip(flags, row[1:], strict=True) if n}

    issues = await client.query(
        "SELECT check, severity, action, count() AS n FROM data_quality_log "
        "WHERE toDate(ts) = {day:Date} GROUP BY check, severity, action ORDER BY n DESC",
        parameters=params,
    )
    return QualityReport(
        runs_by_status=by_status,
        completeness=received / expected if expected else 0.0,
        ticks=int(row[0]),
        flag_counts=flag_counts,
        issues=[(str(c), str(s), str(a), int(n)) for c, s, a, n in issues.result_rows],
    )
