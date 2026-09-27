#!/usr/bin/env python3
"""Record real TSETMC / Fipiran responses as test fixtures.

Standard library only, so it runs without installing the project:

    python3 scripts/capture_fixtures.py            # default sample funds
    python3 scripts/capture_fixtures.py --ins 123   # extra instrument codes

TSETMC rejects most non-Iranian IPs, so run this with any VPN turned off.
Every response (successful or not) is written to ``tests/fixtures/captured/<source>/``
together with a ``manifest.json`` describing status codes and latencies.
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

TSETMC = "https://cdn.tsetmc.com/api"
FIPIRAN = "https://fund.fipiran.ir/api/v1"
OLD_TSETMC = "http://old.tsetmc.com/tsev2/data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
}

# Symbols used to discover sample instrument codes: plain equity, leveraged,
# index and a fixed-income ETF (as a negative example for classification).
SAMPLE_SYMBOLS = ["اطلس", "آگاس", "اهرم", "دارا یکم", "یاقوت"]

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "captured"


@dataclass
class Record:
    name: str
    url: str
    status: int
    latency_ms: int
    bytes: int
    file: str
    error: str = ""


def fetch(url: str, timeout: float) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read(), ""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b"", f"HTTPError: {exc.reason}"
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        return 0, b"", f"{type(exc).__name__}: {exc}"


class Recorder:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.records: list[Record] = []

    def get(self, source: str, name: str, url: str) -> object | None:
        started = time.perf_counter()
        status, body, error = fetch(url, self.timeout)
        latency = int((time.perf_counter() - started) * 1000)

        folder = ROOT / source
        folder.mkdir(parents=True, exist_ok=True)
        parsed: object | None = None
        try:
            parsed = json.loads(body.decode("utf-8"))
            path = folder / f"{name}.json"
            path.write_text(json.dumps(parsed, ensure_ascii=False, indent=1), "utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError):
            path = folder / f"{name}.txt"
            path.write_bytes(body)

        rec = Record(name, url, status, latency, len(body), str(path.relative_to(ROOT)), error)
        self.records.append(rec)
        mark = "OK " if status == 200 and not error else "ERR"
        print(f"[{mark}] {status:>3} {latency:>6}ms {len(body):>9}B  {source}/{name}  {error}")
        return parsed

    def write_manifest(self) -> Path:
        path = ROOT / "manifest.json"
        payload = {
            "captured_at": datetime.now(UTC).isoformat(),
            "records": [asdict(r) for r in self.records],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
        return path


def find_ins_code(search_result: object, symbol: str) -> str | None:
    """Pick the instrument whose symbol matches exactly (field names vary)."""
    if not isinstance(search_result, dict):
        return None
    items = next((v for v in search_result.values() if isinstance(v, list)), [])
    for item in items:
        if not isinstance(item, dict):
            continue
        sym = item.get("lVal18AFC") or item.get("symbol") or ""
        code = item.get("insCode") or item.get("ins_code")
        if code and sym.strip() == symbol:
            return str(code)
    first = items[0] if items and isinstance(items[0], dict) else {}
    return str(first["insCode"]) if first.get("insCode") else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ins", nargs="*", default=[], help="extra TSETMC insCodes")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    rec = Recorder(args.timeout)

    # 1) Bulk endpoints (what the per-minute collector would ideally use).
    rec.get("fipiran", "fundcompare", f"{FIPIRAN}/fund/fundcompare")
    mw_params = urllib.parse.urlencode(
        {
            "market": 0,
            "industrialGroup": "",
            "paperTypes[0]": 1,
            "paperTypes[1]": 2,
            "paperTypes[2]": 3,
            "paperTypes[3]": 4,
            "paperTypes[4]": 5,
            "paperTypes[5]": 6,
            "paperTypes[6]": 7,
            "paperTypes[7]": 8,
            "paperTypes[8]": 9,
            "showTraded": "false",
            "withBestLimits": "true",
            "hEven": 0,
            "RefID": 0,
        }
    )
    rec.get("tsetmc", "market_watch", f"{TSETMC}/ClosingPrice/GetMarketWatch?{mw_params}")
    rec.get("tsetmc", "client_type_all", f"{TSETMC}/ClientType/GetClientTypeAll")
    rec.get("tsetmc", "market_overview", f"{TSETMC}/MarketData/GetMarketOverview/1")
    rec.get("tsetmc_old", "market_watch_plus", f"{OLD_TSETMC}/MarketWatchPlus.aspx")
    rec.get("tsetmc_old", "client_type_all", f"{OLD_TSETMC}/ClientTypeAll.aspx")

    # 2) Discover sample instrument codes.
    ins_codes: dict[str, str] = {code: code for code in args.ins}
    for i, symbol in enumerate(SAMPLE_SYMBOLS):
        quoted = urllib.parse.quote(symbol)
        result = rec.get(
            "tsetmc", f"search_{i}", f"{TSETMC}/Instrument/GetInstrumentSearch/{quoted}"
        )
        code = find_ins_code(result, symbol)
        if code:
            ins_codes[code] = symbol

    # 3) Per-instrument endpoints.
    for code in ins_codes:
        per_ins = {
            "instrument_info": f"Instrument/GetInstrumentInfo/{code}",
            "closing_price_info": f"ClosingPrice/GetClosingPriceInfo/{code}",
            "client_type": f"ClientType/GetClientType/{code}/1/0",
            "best_limits": f"BestLimits/{code}",
            "etf": f"Fund/GetETFByInsCode/{code}",
            "daily_history": f"ClosingPrice/GetClosingPriceDailyList/{code}/0",
            "client_type_history": f"ClientType/GetClientTypeHistory/{code}",
            "trades_today": f"Trade/GetTrade/{code}",
        }
        for name, path in per_ins.items():
            rec.get("tsetmc", f"{name}_{code}", f"{TSETMC}/{path}")
            time.sleep(0.3)  # be polite

    manifest = rec.write_manifest()
    ok = sum(1 for r in rec.records if r.status == 200 and not r.error)
    print(f"\n{ok}/{len(rec.records)} succeeded. Manifest: {manifest}")
    print("Samples:", json.dumps(ins_codes, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
