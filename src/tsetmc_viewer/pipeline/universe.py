"""The fund universe: which instruments the per-minute collector tracks.

Rebuilt once per trading day (fund lists change: new funds IPO, old ones
convert or liquidate) and cached in memory for the rest of the day
(cache layer ① in ADR 0006).

Sync steps
1. Market watch → primary fund boards (sector 68, ISIN IRT…0001).
2. ``GetInstrumentInfo`` for each → official fund description + units issued.
3. Classify, upsert ``funds`` (all fund types, for context) and ``fund_daily``
   (units). Funds that disappeared are soft-deactivated, never deleted.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID, uuid4

from tsetmc_viewer.clock import MarketClock
from tsetmc_viewer.domain.funds import FundRef, classify_fund, is_fund_unit, is_primary_board
from tsetmc_viewer.sources.http import RawResponse, SourceError
from tsetmc_viewer.sources.tsetmc import TsetmcClient
from tsetmc_viewer.sources.tsetmc_models import (
    InstrumentInfo,
    PayloadError,
    parse_instrument_info,
    parse_market_watch,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FundRecord:
    ref: FundRef
    market: str
    board: str
    is_active: bool = True


class UniverseStore(Protocol):
    async def insert_raw(self, run_id: UUID, responses: Sequence[RawResponse]) -> int: ...
    async def upsert_funds(self, records: Sequence[FundRecord], at: datetime) -> None: ...
    async def insert_fund_units(
        self, day: date, units: Mapping[str, int], at: datetime
    ) -> None: ...
    async def load_funds(self, synced_on: date | None = None) -> list[FundRef]: ...


class UniverseError(RuntimeError):
    pass


class UniverseSync:
    def __init__(self, tsetmc: TsetmcClient, store: UniverseStore, clock: MarketClock) -> None:
        self._tsetmc = tsetmc
        self._store = store
        self._clock = clock

    async def sync(self) -> list[FundRef]:
        run_id = uuid4()
        watch_raw = await self._tsetmc.market_watch()
        responses: list[RawResponse] = [watch_raw]
        if not watch_raw.ok:
            await self._store.insert_raw(run_id, responses)
            raise UniverseError(f"market watch returned HTTP {watch_raw.status_code}")

        primaries = [
            r
            for r in parse_market_watch(watch_raw.json())
            if is_fund_unit(r.isin, r.sector) and is_primary_board(r.isin)
        ]
        infos = await asyncio.gather(
            *(self._tsetmc.instrument_info(r.ins_code) for r in primaries), return_exceptions=True
        )

        records: list[FundRecord] = []
        units: dict[str, int] = {}
        for row, result in zip(primaries, infos, strict=True):
            info: InstrumentInfo | None = None
            if isinstance(result, RawResponse):
                responses.append(result)
                if result.ok:
                    try:
                        info = parse_instrument_info(result.json())
                    except (PayloadError, ValueError):
                        log.warning("bad instrument info", extra={"ins_code": row.ins_code})
            elif not isinstance(result, SourceError):
                raise result
            fund_type = classify_fund(info.fund_desc if info else None, row.name, row.isin)
            ref = FundRef(
                ins_code=row.ins_code,
                symbol=row.symbol,
                name=info.name if info else row.name,
                isin=row.isin,
                fund_type=fund_type,
                units=info.units if info and info.units > 0 else None,
            )
            records.append(FundRecord(ref, info.market if info else "", info.board if info else ""))
            if ref.units:
                units[ref.ins_code] = ref.units

        # Soft-deactivate funds that vanished from the market watch.
        seen = {r.ref.ins_code for r in records}
        gone = [r for r in await self._store.load_funds() if r.ins_code not in seen]
        records += [FundRecord(ref, "", "", is_active=False) for ref in gone]

        now = self._clock.now()
        await self._store.insert_raw(run_id, responses)
        await self._store.upsert_funds(records, now)
        await self._store.insert_fund_units(now.date(), units, now)
        refs = [r.ref for r in records if r.is_active]
        log.info(
            "universe synced",
            extra={
                "funds": len(refs),
                "equity": sum(r.fund_type.is_equity for r in refs),
                "deactivated": len(gone),
                "info_failures": sum(1 for r in records if r.is_active and not r.market),
            },
        )
        return refs


class FundUniverse:
    """Equity-fund universe for today, cached in memory."""

    def __init__(self, sync: UniverseSync, store: UniverseStore) -> None:
        self._sync = sync
        self._store = store
        self._day: date | None = None
        self._funds: dict[str, FundRef] = {}

    @property
    def funds(self) -> Mapping[str, FundRef]:
        return self._funds

    def _set(self, day: date, refs: Sequence[FundRef]) -> Mapping[str, FundRef]:
        self._day = day
        self._funds = {r.ins_code: r for r in refs if r.fund_type.is_equity}
        return self._funds

    async def get(self, today: date) -> Mapping[str, FundRef]:
        if self._day == today and self._funds:
            return self._funds
        stored = await self._store.load_funds(synced_on=today)
        if stored:
            return self._set(today, stored)
        try:
            return self._set(today, await self._sync.sync())
        except (SourceError, UniverseError) as exc:
            fallback = await self._store.load_funds()
            if not fallback:
                raise UniverseError("no fund universe available") from exc
            log.warning("universe sync failed, using last known list", extra={"error": str(exc)})
            # Do not mark as synced: retry on the next cycle.
            self._funds = {r.ins_code: r for r in fallback if r.fund_type.is_equity}
            return self._funds
