#!/usr/bin/env python3
"""Capture reference data and history that do not need an open market.

Run any time with the VPN turned off (standard library only, ~3–5 minutes):

    python3 scripts/capture_offhours.py

What it records (``tests/fixtures/captured/offhours/``, gzip-compressed JSON):

* ``instrument_info.json.gz``  instrument info of EVERY primary fund board
  → real fund-type distribution, classification coverage, units issued
* ``etf.json.gz``              latest NAV of every fund → NAV timestamps, bubble per type
* ``daily_history.json.gz``    last 400 daily closes of each equity fund → returns backfill
* ``client_history.json.gz``   last 400 days of official individual/institutional rial flows
* ``summary.json``             counts, fund-type table, failures (small, human-readable)
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

API = "https://cdn.tsetmc.com/api"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "captured" / "offhours"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tsetmc.com/",
}
WORKERS = 6
HISTORY_DAYS = 400


def get_json(path: str, retries: int = 3) -> Any:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{API}/{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries - 1:
                return {"__error__": f"{type(exc).__name__}: {exc}"}
            time.sleep(1.5 * (attempt + 1))
    return None


def fetch_all(paths: dict[str, str], label: str) -> dict[str, Any]:
    started = time.perf_counter()
    with ThreadPoolExecutor(WORKERS) as pool:
        results = dict(zip(paths, pool.map(get_json, paths.values()), strict=True))
    failed = sum(1 for v in results.values() if isinstance(v, dict) and "__error__" in v)
    print(f"  {label:<16} {len(results) - failed}/{len(results)} ok  "
          f"{time.perf_counter() - started:5.1f}s")  # fmt: skip
    return results


def save(name: str, obj: Any) -> None:
    with gzip.open(OUT / name, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def recent(results: dict[str, Any], key: str) -> dict[str, Any]:
    """Keep only the newest HISTORY_DAYS rows of each history response."""
    return {
        code: (v.get(key) or [])[:HISTORY_DAYS] if isinstance(v, dict) and key in v else v
        for code, v in results.items()
    }


def is_equity(info: Any) -> bool:
    desc = str((info or {}).get("instrumentInfo", {}).get("faraDesc") or "")
    return "سهام" in desc.replace("ي", "ی")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    params = {"market": 0, "industrialGroup": "", "showTraded": "false",
              "withBestLimits": "false", "hEven": 0, "RefID": 0}  # fmt: skip
    params |= {f"paperTypes[{i}]": p for i, p in enumerate(range(1, 10))}
    print("market watch …")
    watch = get_json(f"ClosingPrice/GetMarketWatch?{urllib.parse.urlencode(params)}")
    if not isinstance(watch, dict) or "marketwatch" not in watch:
        print(f"market watch failed: {watch}. Is the VPN off?")
        return 1
    primaries = {
        r["insCode"]: r["lva"]
        for r in watch["marketwatch"]
        if str(r.get("csv", "")).strip() == "68"
        and str(r.get("insID", "")).startswith("IRT")
        and str(r.get("insID", "")).endswith("0001")
    }
    print(f"  {len(primaries)} primary fund boards")

    infos = fetch_all(
        {c: f"Instrument/GetInstrumentInfo/{c}" for c in primaries}, "instrument info"
    )
    save("instrument_info.json.gz", infos)
    etfs = fetch_all({c: f"Fund/GetETFByInsCode/{c}" for c in primaries}, "ETF NAV")
    save("etf.json.gz", etfs)

    equity = [c for c in primaries if is_equity(infos.get(c))]
    print(f"  {len(equity)} equity funds → history")
    daily = fetch_all(
        {c: f"ClosingPrice/GetClosingPriceDailyList/{c}/0" for c in equity}, "daily history"
    )
    save("daily_history.json.gz", recent(daily, "closingPriceDaily"))
    flows = fetch_all({c: f"ClientType/GetClientTypeHistory/{c}" for c in equity}, "client history")
    save("client_history.json.gz", recent(flows, "clientType"))

    descs = Counter(
        str(v.get("instrumentInfo", {}).get("faraDesc") or "∅")
        for v in infos.values()
        if isinstance(v, dict) and "instrumentInfo" in v
    )
    summary = {
        "primary_boards": len(primaries),
        "equity_funds": len(equity),
        "fara_desc_counts": descs.most_common(),
        "equity_symbols": sorted(primaries[c] for c in equity),
        "failures": {
            kind: [c for c, v in res.items() if isinstance(v, dict) and "__error__" in v]
            for kind, res in (("info", infos), ("etf", etfs), ("daily", daily), ("flows", flows))
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
    print(f"\nDone: {len(equity)} equity funds out of {len(primaries)}. Saved to {OUT}")
    for desc, n in descs.most_common(12):
        print(f"  {n:>4}  {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
