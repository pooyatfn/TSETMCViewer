"""Load test of the panel's read path: N virtual users refreshing the dashboard.

Each virtual user repeatedly requests the six endpoints the dashboard loads after
every tick, like a browser would. Three scenarios show what each cache layer buys
(ADR 0006):

  --mode plain     no conditional requests (each response is computed or read from Redis)
  --mode etag      browser behaviour: If-None-Match with the last ETag → 304 when unchanged

Run once with the API started with ``REDIS_URL=`` (no cache) and once with Redis.

    uv run python scripts/loadtest.py --base http://localhost:8000 --users 20 --seconds 20
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter, defaultdict

import httpx

DASHBOARD = [
    "/api/v1/overview",
    "/api/v1/funds",
    "/api/v1/market/flow",
    "/api/v1/flows/daily?days=60",
    "/api/v1/returns",
    "/api/v1/quality",
]


async def user(
    client: httpx.AsyncClient,
    deadline: float,
    etag: bool,
    lat: dict[str, list[float]],
    codes: Counter[int],
    cache: Counter[str],
) -> None:
    etags: dict[str, str] = {}
    while time.perf_counter() < deadline:
        for path in DASHBOARD:
            headers = {"If-None-Match": etags[path]} if etag and path in etags else {}
            t0 = time.perf_counter()
            r = await client.get(path, headers=headers)
            lat[path].append((time.perf_counter() - t0) * 1000)
            codes[r.status_code] += 1
            cache[r.headers.get("x-cache", "304" if r.status_code == 304 else "-")] += 1
            if "etag" in r.headers:
                etags[path] = r.headers["etag"]


def pct(values: list[float], p: float) -> float:
    return statistics.quantiles(values, n=100)[int(p) - 1] if len(values) > 1 else values[0]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--mode", choices=["plain", "etag"], default="plain")
    args = ap.parse_args()

    lat: dict[str, list[float]] = defaultdict(list)
    codes: Counter[int] = Counter()
    cache: Counter[str] = Counter()
    limits = httpx.Limits(max_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base, limits=limits, timeout=30) as client:
        await client.get("/health")
        start = time.perf_counter()
        deadline = start + args.seconds
        await asyncio.gather(
            *(
                user(client, deadline, args.mode == "etag", lat, codes, cache)
                for _ in range(args.users)
            )
        )
        elapsed = time.perf_counter() - start

    total = sum(len(v) for v in lat.values())
    every = [x for v in lat.values() for x in v]
    print(f"mode={args.mode} users={args.users} seconds={elapsed:.1f}")
    print(f"requests={total}  throughput={total / elapsed:.0f} req/s")
    print(f"status={dict(codes)}  cache={dict(cache)}")
    print(f"{'endpoint':<32}{'n':>7}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}")
    for path in DASHBOARD:
        v = lat[path]
        print(f"{path:<32}{len(v):>7}{pct(v, 50):>9.1f}{pct(v, 95):>9.1f}{pct(v, 99):>9.1f}")
    print(
        f"{'ALL':<32}{total:>7}{pct(every, 50):>9.1f}{pct(every, 95):>9.1f}{pct(every, 99):>9.1f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
