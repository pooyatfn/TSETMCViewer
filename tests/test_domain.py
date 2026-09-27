from __future__ import annotations

import pytest

from tsetmc_viewer.domain.funds import (
    FundType,
    classify_fund,
    is_fund_unit,
    is_primary_board,
    isin_stem,
)
from tsetmc_viewer.domain.quality import QualityFlag
from tsetmc_viewer.domain.text import normalize_fa


def test_normalize_unifies_arabic_letters_and_spaces() -> None:
    assert normalize_fa("  نوع صندوق:  سهامي  اهرمي ") == "نوع صندوق: سهامی اهرمی"
    assert normalize_fa("دارا يكم") == "دارا یکم"
    assert normalize_fa(None) == ""


@pytest.mark.parametrize(
    ("fara_desc", "name", "isin", "expected"),
    [
        # verbatim faraDesc values recorded from TSETMC
        ("نوع صندوق : سهامی", "صندوق س.توسعه اطلس مفيد-س", "IRT3SATF0001", FundType.EQUITY),
        ("نوع صندوق: سهامي", "صندوق واسطه گري مالي يكم-سهام", "IRT1DARA0001", FundType.EQUITY),
        ("نوع صندوق: سهامي اهرمي", "صندوق س.اهرمي مفيد", "IRT1AHRM0001", FundType.LEVERAGED),
        (
            "نوع صندوق: در اوراق بهادار با درآمد ثابت",
            "صندوق س.ياقوت آگاه",
            "IRT1YGHT0001",
            FundType.FIXED_INCOME,
        ),
        # name-based refinement of plain "سهامی"
        ("نوع صندوق: سهامی", "صندوق س.شاخصي كيان", "IRT1XXXX0001", FundType.INDEX),
        ("نوع صندوق: سهامی", "صندوق س.بخشي پتروشيمي", "IRT1XXXX0001", FundType.SECTOR),
        ("نوع صندوق: مختلط", "", "IRT1XXXX0001", FundType.MIXED),
        # commodity funds are recognised by ISIN even without a description
        (None, "صندوق س.كالاي صبا", "IRTKNAFS0001", FundType.COMMODITY),
        (None, "", "IRT1XXXX0001", FundType.OTHER),
    ],
)
def test_classify_fund(fara_desc: str | None, name: str, isin: str, expected: FundType) -> None:
    assert classify_fund(fara_desc, name, isin) is expected


def test_equity_family() -> None:
    equity = {t for t in FundType if t.is_equity}
    assert equity == {FundType.EQUITY, FundType.INDEX, FundType.SECTOR, FundType.LEVERAGED}


@pytest.mark.parametrize(
    ("isin", "sector", "unit", "primary"),
    [
        ("IRT3SATF0001", "68 ", True, True),  # اطلس
        ("IRT3SAHF0002", "68", True, False),  # secondary board
        ("IROASATF8461", "68", False, False),  # option on اطلس
        ("IRO1FOLD0001", "27", False, True),  # a stock
    ],
)
def test_fund_unit_and_board(isin: str, sector: str, unit: bool, primary: bool) -> None:
    assert is_fund_unit(isin, sector) is unit
    assert is_primary_board(isin) is primary


def test_isin_stem_links_boards_of_one_fund() -> None:
    assert isin_stem("IRT1YGHT0001") == isin_stem("IRT1YGHT0004") == "IRT1YGHT"


def test_quality_flag_names() -> None:
    flags = QualityFlag.NAV_MISSING | QualityFlag.NO_TRADES
    assert flags.names() == ["NAV_MISSING", "NO_TRADES"]


# --- the full real catalog (333 primary fund boards, recorded 2 Mehr 1405) -----------


def _catalog() -> list[dict[str, str]]:
    import json
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "sample" / "fund_catalog.json"
    return json.loads(path.read_text("utf-8"))  # type: ignore[no-any-return]


def test_name_convention_agrees_with_official_type() -> None:
    """The fallback (name only) must match faraDesc wherever both exist."""
    both = [r for r in _catalog() if r["fara_desc"]]
    disagree = [
        r["symbol"]
        for r in both
        if classify_fund(None, r["name"], r["isin"])
        is not classify_fund(r["fara_desc"], r["name"], r["isin"])
    ]
    assert len(both) == 252
    # Two fixed-income funds carry no hint in their name; they fall back to OTHER,
    # which is safe: the fallback never turns a non-equity fund into an equity one.
    assert sorted(disagree) == ["ارمغان", "پارند"]


def test_catalog_equity_family_size() -> None:
    types = [classify_fund(r["fara_desc"], r["name"], r["isin"]) for r in _catalog()]
    assert sum(t.is_equity for t in types) == 159
    assert types.count(FundType.LEVERAGED) == 9
    assert types.count(FundType.COMMODITY) == 52


def test_empty_description_uses_name_suffix() -> None:
    assert classify_fund("", "صندوق س.بخشي صنايع آسمان1-ب", "IRT3BNKF0001") is FundType.SECTOR
    assert classify_fund(None, "صندوق س.آوان ژرف آگاه-س", "IRT3VANF0001") is FundType.EQUITY
    assert classify_fund(None, "ص.س.درآمد ثابت آسال-د", "IRT3ASLF0001") is FundType.FIXED_INCOME
