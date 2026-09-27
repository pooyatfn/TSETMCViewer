"""The backfill probe's sampling and extrapolation (scripts/probe_backfill.py).

The probe runs against the real TSETMC by hand; these tests make sure the
numbers it prints are computed correctly from whatever it measures.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx

ROOT = Path(__file__).resolve().parent.parent


def _probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "probe_backfill", ROOT / "scripts/probe_backfill.py"
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


p = _probe()


def funds(counts: list[int]) -> list[object]:
    return [p.Fund(str(i), f"s{i}", c) for i, c in enumerate(counts)]


def test_sample_keeps_the_busiest_and_spans_the_rest() -> None:
    population = funds(list(range(100, 0, -1)))  # trade counts 100..1
    sample = p.stratified_sample(population, 10, busiest=3)
    counts = [f.trade_count for f in sample]
    assert counts[:3] == [100, 99, 98]
    assert counts[3] == 97  # both ends of the remaining range
    assert counts[-1] == 1
    assert len(set(counts)) == 10


def test_sample_larger_than_population_returns_everything() -> None:
    assert len(p.stratified_sample(funds([3, 2, 1]), 10)) == 3


def test_interpolate_is_linear_and_clamped() -> None:
    points = [(0.0, 1.0), (100.0, 11.0)]
    assert p.interpolate(50, points) == 6.0
    assert p.interpolate(-5, points) == 1.0
    assert p.interpolate(500, points) == 11.0


def test_makespan_is_bounded_by_the_longest_job() -> None:
    assert p.makespan([10, 1, 1, 1], 4) == 10
    assert p.makespan([2, 2, 2, 2], 2) == 4
    assert p.makespan([5, 5], 1) == 10


def _result(trades: int, latency: float, mb: float, status: int = 200) -> object:
    return p.Result("trades", "x", "x", trades, status, latency, int(mb * 1e6), 0, 1)


def test_estimate_extrapolates_by_trade_count() -> None:
    sample = [_result(1000, 10.0, 2.0), _result(10, 1.0, 0.02), _result(500, 0, 0, status=500)]
    population = funds([1000, 1000, 505, 10, 10])
    est = p.estimate(sample, population, concurrency=2, observed_wall_s=10.0)
    assert est["errors"] == 1
    all_funds = est["all_funds"]
    # 505 trades lies halfway between the two good points: 5.5 s, 1.01 MB.
    assert all_funds["total_wire_mb"] == round((2 + 2 + 1.01 + 0.02 + 0.02), 1)
    assert all_funds["sequential_min"] == round((10 + 10 + 5.5 + 1 + 1) / 60, 1)


def test_estimate_reports_unusable_endpoint() -> None:
    est = p.estimate([_result(1, 0, 0, status=404)], funds([1]), concurrency=1, observed_wall_s=1)
    assert est == {"usable": False, "errors": 1, "empty": 0}


def test_estimate_rejects_endpoints_that_answer_200_with_no_rows() -> None:
    """Real run, 1405/07/04: GetClosingPriceHistory said 200 + `[]` for funds with 19k trades."""
    empty = p.Result("price_history", "x", "x", 19282, 200, 0.3, 46, 26, 0)
    est = p.estimate([empty], funds([19282]), concurrency=8, observed_wall_s=0.3)
    assert est == {"usable": False, "errors": 0, "empty": 1}


def test_fetch_records_rows_and_time_span() -> None:
    body = json.dumps({"trade": [{"hEven": 90012, "nTran": 1}, {"hEven": 113000, "nTran": 2}]})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/Trade/GetTrade/42")
        return httpx.Response(200, content=body.encode())

    async def run() -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result, _ = await p.fetch(
                client, asyncio.Semaphore(1), "trades", p.Fund("42", "x", 2), "20260926"
            )
            return result

    result = asyncio.run(run())
    assert result.ok
    assert result.rows == 2
    assert (result.first_heven, result.last_heven) == (90012, 113000)
    assert result.row_keys == ["hEven", "nTran"]
