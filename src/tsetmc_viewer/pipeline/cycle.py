"""Raw responses of one cycle → parsed payloads → ticks.

Shared by the live collector and by ``replay``: both feed a list of
``RawResponse`` in and get the same ticks out. That symmetry is what makes
raw-first ingestion (ADR 0003) useful.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from tsetmc_viewer.domain.funds import FundRef
from tsetmc_viewer.domain.status import FundState
from tsetmc_viewer.pipeline.transform import (
    MarketTick,
    TickBatch,
    build_fund_ticks,
    build_market_tick,
)
from tsetmc_viewer.sources.http import RawResponse
from tsetmc_viewer.sources.tsetmc_models import (
    ClientTypeRow,
    EtfNav,
    InstrumentState,
    MarketOverview,
    MarketWatchRow,
    PayloadError,
    parse_client_types,
    parse_etf,
    parse_instrument_state,
    parse_market_overview,
    parse_market_watch,
)

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ParsedCycle:
    market_watch: list[MarketWatchRow] | None = None
    client_types: list[ClientTypeRow] = field(default_factory=list)
    navs: dict[str, EtfNav] = field(default_factory=dict)
    states: dict[str, InstrumentState] = field(default_factory=dict)
    overview: MarketOverview | None = None
    errors: list[str] = field(default_factory=list)


def parse_responses(responses: Sequence[RawResponse]) -> ParsedCycle:
    out = ParsedCycle()
    for r in responses:
        if not r.ok:
            out.errors.append(f"{r.endpoint}:{r.ins_code}: HTTP {r.status_code}")
            continue
        try:
            payload = r.json()
            match r.endpoint:
                case "market_watch":
                    out.market_watch = parse_market_watch(payload)
                case "client_type_all":
                    out.client_types = parse_client_types(payload)
                case "market_overview":
                    out.overview = parse_market_overview(payload)
                case "etf":
                    nav = parse_etf(payload)
                    if nav is not None:
                        out.navs[r.ins_code] = nav
                case "closing_price_info":
                    state = parse_instrument_state(payload)
                    if state is not None:
                        out.states[r.ins_code] = state
                case _:
                    pass
        except (ValueError, PayloadError, ValidationError) as exc:
            # ValidationError subclasses ValueError; listed for readability.
            out.errors.append(f"{r.endpoint}:{r.ins_code}: parse error: {exc}")
            log.warning("parse error", extra={"endpoint": r.endpoint, "ins_code": r.ins_code})
    return out


@dataclass(slots=True)
class CycleResult:
    batch: TickBatch
    market: MarketTick | None
    errors: list[str]
    states: list[FundState] = field(default_factory=list)


def process_cycle(
    *,
    responses: Sequence[RawResponse],
    universe: Mapping[str, FundRef],
    ts: datetime,
    run_id: UUID,
    ingested_at: datetime,
) -> CycleResult:
    parsed = parse_responses(responses)
    states = [
        FundState(ts, ins, s.code, s.title, s.under_supervision, ingested_at)
        for ins, s in parsed.states.items()
        if ins in universe
    ]
    if parsed.market_watch is None:
        # Without prices there is nothing to write; every fund counts as missing.
        return CycleResult(TickBatch(missing=list(universe)), None, parsed.errors, states)
    batch = build_fund_ticks(
        ts=ts,
        run_id=run_id,
        ingested_at=ingested_at,
        universe=universe,
        market_watch=parsed.market_watch,
        client_types=parsed.client_types,
        navs=parsed.navs,
    )
    market = (
        build_market_tick(ts=ts, run_id=run_id, ingested_at=ingested_at, overview=parsed.overview)
        if parsed.overview
        else None
    )
    return CycleResult(batch, market, parsed.errors, states)
