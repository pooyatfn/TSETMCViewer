#!/usr/bin/env python3
"""Build small, committed test fixtures from a full capture.

``capture_fixtures.py`` writes multi-megabyte responses to
``tests/fixtures/captured/`` (git-ignored). This script keeps only what the
tests need and writes it to ``tests/fixtures/sample/``:

- market watch: the sample funds, a few other fund units, a few options on
  funds and a few non-fund instruments (so filters are exercised)
- client types: the same instruments
- per-instrument ETF / instrument-info responses for the sample funds

    python3 scripts/trim_fixtures.py [--src DIR]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def load(path: Path) -> dict:  # type: ignore[type-arg]
    return json.loads(path.read_text("utf-8"))


def dump(obj: object, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=ROOT / "captured" / "tsetmc")
    args = parser.parse_args()
    src: Path = args.src
    out = ROOT / "sample"
    out.mkdir(parents=True, exist_ok=True)

    samples = sorted(p.stem.removeprefix("etf_") for p in src.glob("etf_*.json"))
    rows = load(src / "market_watch.json")["marketwatch"]

    def pick(pred, n):  # type: ignore[no-untyped-def]
        return [r for r in rows if pred(r) and r["insCode"] not in samples][:n]

    keep = [r for r in rows if r["insCode"] in samples]
    keep += pick(lambda r: r["csv"].strip() == "68" and r["insID"].startswith("IRT"), 6)
    keep += pick(lambda r: r["csv"].strip() == "68" and r["insID"].startswith("IRO"), 4)
    keep += pick(lambda r: r["csv"].strip() != "68" and r["qtc"] > 0, 4)
    dump({"marketwatch": keep}, out / "market_watch.json")

    codes = {r["insCode"] for r in keep}
    ct = load(src / "client_type_all.json")["clientTypeAllDto"]
    dump(
        {"clientTypeAllDto": [r for r in ct if r["insCode"] in codes]}, out / "client_type_all.json"
    )

    for pattern in ("etf_*.json", "instrument_info_*.json", "market_overview.json"):
        for f in src.glob(pattern):
            shutil.copy(f, out / f.name)

    print(f"{len(keep)} market-watch rows, samples: {samples} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
