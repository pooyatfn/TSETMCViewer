#!/usr/bin/env python3
"""Measure what it would cost to backfill today's minute data from TSETMC.

The collector only has minute data from the moment it started. TSETMC keeps
per-instrument intraday history for the current day, so a late start could
in principle be backfilled. This script measures how expensive that is on a
**stratified sample** of the fund universe (the busiest funds plus funds
spread across the whole trade-count range) and extrapolates to all funds.

Run with any VPN turned off, ideally during or right after a session
(the payloads grow with the number of trades so far):

    uv run python scripts/probe_backfill.py                   # 40 funds, 4 at a time
    uv run python scripts/probe_backfill.py --concurrency 8   # repeat to see scaling
    uv run python scripts/probe_backfill.py --sample 20 --endpoints trades

Candidate endpoints (each is tried; the summary says which ones work):

- ``trades``: ``Trade/GetTrade/{ins}``, every trade of today
- ``trade_history``: ``Trade/GetTradeHistory/{ins}/{date}/false``, same for a given date
- ``price_history``: ``ClosingPrice/GetClosingPriceHistory/{ins}/{date}``,
  the instrument's price/volume/value state at each change during the day

Output: ``tests/fixtures/captured/backfill/`` (``summary.json`` plus one
compressed response per endpoint for parser work). Nothing is written to
the database.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import itertools
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from tsetmc_viewer.domain.funds import is_fund_unit, is_primary_board
from tsetmc_viewer.sources.tsetmc_models import parse_market_watch

BASE = "https://cdn.tsetmc.com/api"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "captured" / "backfill"
TEHRAN = ZoneInfo("Asia/Tehran")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",  # the Day-1 measurement forgot this (see summary notes)
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
}
ENDPOINTS = {
    "trades": "Trade/GetTrade/{ins}",
    "trade_history": "Trade/GetTradeHistory/{ins}/{date}/false",
    "price_history": "ClosingPrice/GetClosingPriceHistory/{ins}/{date}",
}


@dataclass
class Fund:
    ins_code: str
    symbol: str
    trade_count: int


@dataclass
class Result:
    endpoint: str
    ins_code: str
    symbol: str
    trade_count: int
    status: int
    latency_s: float
    wire_bytes: int
    body_bytes: int
    rows: int
    first_heven: int | None = None
    last_heven: int | None = None
    row_keys: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error


# --- sampling and estimation (pure; unit-tested) -------------------------------


def stratified_sample(funds: list[Fund], size: int, busiest: int = 10) -> list[Fund]:
    """The ``busiest`` funds by trade count, then the rest spread evenly over the ranking."""
    ranked = sorted(funds, key=lambda f: f.trade_count, reverse=True)
    if size >= len(ranked):
        return ranked
    head = ranked[: min(busiest, size)]
    rest = ranked[len(head) :]
    k = size - len(head)
    if k <= 0 or not rest:
        return head
    step = (len(rest) - 1) / max(k - 1, 1)
    picks = sorted({round(i * step) for i in range(k)})
    return head + [rest[i] for i in picks]


def interpolate(x: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear y(x) through ``points`` (sorted by x), clamped at both ends."""
    if not points:
        raise ValueError("no points")
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def makespan(durations: list[float], workers: int) -> float:
    """Wall-clock time for ``durations`` on ``workers`` parallel slots (longest first)."""
    slots = [0.0] * max(workers, 1)
    for d in sorted(durations, reverse=True):
        i = slots.index(min(slots))
        slots[i] += d
    return max(slots)


def estimate(
    results: list[Result],
    population: list[Fund],
    *,
    concurrency: int,
    observed_wall_s: float,
) -> dict[str, Any]:
    """Extrapolate one endpoint's sample to the whole fund universe."""
    ok = [r for r in results if r.ok]
    # A 200 with no rows for a fund that did trade is not data: the first real run
    # showed two of the three candidates answering exactly that for today's date.
    empty = [r for r in ok if r.rows == 0 and r.trade_count > 0]
    if not ok or len(empty) == len([r for r in ok if r.trade_count > 0]):
        return {"usable": False, "errors": len(results) - len(ok), "empty": len(empty)}
    lat = sorted({(float(r.trade_count), r.latency_s) for r in ok})
    size = sorted({(float(r.trade_count), float(r.wire_bytes)) for r in ok})
    est_lat = [interpolate(f.trade_count, lat) for f in population]
    est_bytes = [interpolate(f.trade_count, size) for f in population]
    # How much slower TSETMC got under our own parallel load, measured on the sample.
    ideal_sample = makespan([r.latency_s for r in results], concurrency)
    slowdown = max(observed_wall_s / ideal_sample, 1.0) if ideal_sample else 1.0
    return {
        "usable": True,
        "sample": len(results),
        "errors": len(results) - len(ok),
        "empty": len(empty),
        "error_rate": round(1 - len(ok) / len(results), 3),
        "latency_s": {
            "median": round(sorted(r.latency_s for r in ok)[len(ok) // 2], 2),
            "max": round(max(r.latency_s for r in ok), 2),
        },
        "wire_mb": {
            "median": round(sorted(r.wire_bytes for r in ok)[len(ok) // 2] / 1e6, 3),
            "max": round(max(r.wire_bytes for r in ok) / 1e6, 3),
        },
        "all_funds": {
            "funds": len(population),
            "total_wire_mb": round(sum(est_bytes) / 1e6, 1),
            "sequential_min": round(sum(est_lat) / 60, 1),
            f"parallel_{concurrency}_min": round(makespan(est_lat, concurrency) * slowdown / 60, 1),
            "slowdown_under_load": round(slowdown, 2),
        },
    }


# --- I/O ------------------------------------------------------------------------


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return payload if isinstance(payload, list) else []


async def fetch(
    client: httpx.AsyncClient,
    gate: asyncio.Semaphore,
    endpoint: str,
    fund: Fund,
    date: str,
    base: str = BASE,
) -> tuple[Result, bytes]:
    url = f"{base}/{ENDPOINTS[endpoint].format(ins=fund.ins_code, date=date)}"
    async with gate:
        started = time.perf_counter()
        try:
            resp = await client.get(url)
            body, status, wire, error = (
                resp.content,
                resp.status_code,
                resp.num_bytes_downloaded,
                "",
            )
        except httpx.HTTPError as exc:
            body, status, wire, error = b"", 0, 0, type(exc).__name__
        latency = time.perf_counter() - started
    result = Result(endpoint, fund.ins_code, fund.symbol, fund.trade_count, status,
                    round(latency, 3), wire, len(body), 0, error=error)  # fmt: skip
    if status == 200 and body:
        try:
            rows = _rows(json.loads(body))
        except ValueError:
            result.error = "not json"
        else:
            result.rows = len(rows)
            if rows:
                result.row_keys = sorted(rows[0])
                hevens = [int(r["hEven"]) for r in rows if str(r.get("hEven", "")).isdigit()]
                if hevens:
                    result.first_heven, result.last_heven = min(hevens), max(hevens)
    tag = "ok " if result.ok else "ERR"
    print(f"  {tag} {endpoint:<14} {fund.symbol:<12} trades={fund.trade_count:>6} "
          f"{latency:6.1f}s {wire / 1e6:7.2f} MB rows={result.rows:>6} {result.error}")  # fmt: skip
    return result, body


async def universe(client: httpx.AsyncClient, base: str = BASE) -> list[Fund]:
    params: dict[str, Any] = {"market": 0, "industrialGroup": "", "showTraded": "false",
                              "withBestLimits": "false", "hEven": 0, "RefID": 0}  # fmt: skip
    params |= {f"paperTypes[{i}]": p for i, p in enumerate(range(1, 10))}
    resp = await client.get(f"{base}/ClosingPrice/GetMarketWatch", params=params)
    resp.raise_for_status()
    return [
        Fund(r.ins_code, r.symbol, r.trade_count)
        for r in parse_market_watch(resp.json())
        if is_fund_unit(r.isin, r.sector) and is_primary_board(r.isin)
    ]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=40)
    parser.add_argument("--busiest", type=int, default=10, help="always include the N busiest")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--base", default=BASE, help="API root (tests point this at a fake)")
    parser.add_argument("--date", default=datetime.now(TEHRAN).strftime("%Y%m%d"))
    parser.add_argument("--endpoints", nargs="+", default=list(ENDPOINTS), choices=list(ENDPOINTS))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    limits = httpx.Limits(max_connections=args.concurrency)
    async with httpx.AsyncClient(headers=HEADERS, timeout=args.timeout, limits=limits) as client:
        population = await universe(client, args.base)
        sample = stratified_sample(population, args.sample, args.busiest)
        print(f"{len(population)} funds; sampling {len(sample)} at concurrency {args.concurrency}")
        gate = asyncio.Semaphore(args.concurrency)
        report: dict[str, Any] = {
            "measured_at": datetime.now(TEHRAN).isoformat(timespec="seconds"),
            "date": args.date,
            "concurrency": args.concurrency,
            "population_trades": sorted((f.trade_count for f in population), reverse=True),
            "endpoints": {},
        }
        for endpoint in args.endpoints:
            print(f"\n{endpoint}: {ENDPOINTS[endpoint]}")
            started = time.perf_counter()
            pairs = await asyncio.gather(
                *(fetch(client, gate, endpoint, f, args.date, args.base) for f in sample)
            )
            wall = time.perf_counter() - started
            results = [r for r, _ in pairs]
            # Keep the median-sized successful response for parser work.
            good = sorted((p for p in pairs if p[0].ok), key=lambda p: p[0].wire_bytes)
            if good:
                (OUT / f"{endpoint}.json.gz").write_bytes(gzip.compress(good[len(good) // 2][1]))
            est = estimate(results, population, concurrency=args.concurrency, observed_wall_s=wall)
            report["endpoints"][endpoint] = {
                "path": ENDPOINTS[endpoint],
                "sample_wall_s": round(wall, 1),
                "estimate": est,
                "results": [asdict(r) for r in results],
            }
            print(
                f"  → {json.dumps(est['all_funds'] if est['usable'] else est, ensure_ascii=False)}"
            )
            await asyncio.sleep(5)  # breathe between endpoints

    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nWritten: {OUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
