#!/usr/bin/env python3
"""Measure whether TSETMC can send market-watch *changes* instead of full snapshots.

Run DURING MARKET HOURS (Sat–Wed 09:00–12:30 Tehran) with any VPN turned off:

    python3 scripts/probe_delta.py            # 4 rounds, 60 s apart
    python3 scripts/probe_delta.py --rounds 2 --gap 30

For both the new JSON API and the legacy MarketWatchPlus endpoint it fetches a
full snapshot, then asks for changes since that snapshot and records size,
latency and row counts. Standard library only. Output:
``tests/fixtures/captured/delta/`` (responses) and ``summary.json``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "captured" / "delta"
NEW = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
OLD = "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip",
    "Referer": "https://www.tsetmc.com/",
}


def get(url: str, timeout: float) -> tuple[int, bytes, int, int]:
    """Return (status, decoded body, bytes on the wire, latency ms)."""
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            wire = r.read()
            status = r.status
    except urllib.error.HTTPError as exc:
        wire, status = exc.read() or b"", exc.code
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  ! {exc}")
        return 0, b"", 0, int((time.perf_counter() - started) * 1000)
    latency = int((time.perf_counter() - started) * 1000)
    body = gzip.decompress(wire) if wire[:2] == b"\x1f\x8b" else wire
    return status, body, len(wire), latency


def new_params(heven: int, ref_id: int) -> str:
    params = {
        "market": 0,
        "industrialGroup": "",
        "showTraded": "false",
        "withBestLimits": "true",
        "hEven": heven,
        "RefID": ref_id,
    }
    params |= {f"paperTypes[{i}]": p for i, p in enumerate(range(1, 10))}
    return urllib.parse.urlencode(params)


def new_cursor(body: bytes) -> tuple[int, int, int]:
    """(rows, max hEven, max best-limit rid) of a new-API response."""
    rows = json.loads(body).get("marketwatch", [])
    heven = max((r.get("hEven", 0) for r in rows), default=0)
    rid = max((b.get("rid", 0) for r in rows for b in r.get("blDs") or []), default=0)
    return len(rows), heven, rid


def old_cursor(body: bytes) -> tuple[int, int, int]:
    """(price rows, max heven, refid) of a legacy response.

    Sections are separated by '@': [0] market summary, [2] price rows (';'),
    [3] best limits, [4] RefID. Field 4 of a price row is its HEven.
    """
    parts = body.decode("utf-8", "replace").split("@")
    rows = [x.split(",") for x in parts[2].split(";") if x] if len(parts) > 2 else []
    heven = max((int(r[4]) for r in rows if len(r) > 4 and r[4].isdigit()), default=0)
    ref = int(parts[4]) if len(parts) > 4 and parts[4].strip().isdigit() else 0
    return len(rows), heven, ref


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--gap", type=float, default=60)
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []

    for api, base, fmt, cursor in (
        ("new", NEW, lambda h, r: new_params(h, r), new_cursor),
        ("old", OLD, lambda h, r: urllib.parse.urlencode({"h": h, "r": r}), old_cursor),
    ):
        heven = ref = 0
        for rnd in range(args.rounds):
            url = f"{base}?{fmt(heven, ref)}"
            status, body, wire, ms = get(url, args.timeout)
            ext = "json" if api == "new" else "txt"
            (OUT / f"{api}_{rnd}.{ext}").write_bytes(body)
            try:
                rows, heven, ref = cursor(body)
            except (ValueError, KeyError, IndexError):
                rows = -1
            rec = {
                "api": api,
                "round": rnd,
                "status": status,
                "rows": rows,
                "wire_bytes": wire,
                "body_bytes": len(body),
                "latency_ms": ms,
                "cursor": [heven, ref],
                "at": datetime.now(UTC).isoformat(),
            }
            summary.append(rec)
            print(
                f"{api} #{rnd}: HTTP {status}  rows={rows:>5}  wire={wire / 1024:>8.1f} KB  "
                f"{ms:>6} ms  next cursor h={heven} r={ref}"
            )
            if rnd < args.rounds - 1:
                time.sleep(args.gap)

    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), "utf-8")
    print(f"\nSaved to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
