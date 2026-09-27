"""What a fund is, and how we tell fund types apart.

Identification rules (derived from real TSETMC responses, see docs/02):

* Fund units live in sector ``68`` and have an ISIN starting with ``IRT``
  (``IRT1`` = TSE, ``IRT3`` = IFB, ``IRTK`` = commodity funds). Options on
  funds share sector 68 but have ``IRO*`` ISINs.
* A fund trades on a *primary* board (ISIN ending ``0001``) and may also have
  secondary boards (block trades etc., ``…0002``, ``…0004``) that share the
  ISIN stem. Fund-level data (NAV, type) is keyed by the primary instrument;
  secondary-board turnover is rolled up into it.
* The fund type comes from ``instrumentInfo.faraDesc`` ("نوع صندوق : سهامی").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from tsetmc_viewer.domain.text import normalize_fa

FUND_SECTOR = "68"
PRIMARY_BOARD_SUFFIX = "0001"


class FundType(StrEnum):
    EQUITY = "equity"
    INDEX = "index"
    SECTOR = "sector"
    LEVERAGED = "leveraged"
    FIXED_INCOME = "fixed_income"
    MIXED = "mixed"
    COMMODITY = "commodity"
    OTHER = "other"

    @property
    def is_equity(self) -> bool:
        return self in _EQUITY_TYPES

    @property
    def label_fa(self) -> str:
        return _LABELS_FA[self]


_EQUITY_TYPES = frozenset({FundType.EQUITY, FundType.INDEX, FundType.SECTOR, FundType.LEVERAGED})
_LABELS_FA = {
    FundType.EQUITY: "سهامی",
    FundType.INDEX: "شاخصی",
    FundType.SECTOR: "بخشی",
    FundType.LEVERAGED: "اهرمی",
    FundType.FIXED_INCOME: "درآمد ثابت",
    FundType.MIXED: "مختلط",
    FundType.COMMODITY: "کالایی",
    FundType.OTHER: "سایر",
}

# Ordered: the first matching keyword wins, so the specific ones come first.
_KEYWORDS: tuple[tuple[str, FundType], ...] = (
    ("اهرم", FundType.LEVERAGED),
    ("شاخص", FundType.INDEX),
    ("بخشی", FundType.SECTOR),
    ("درآمد ثابت", FundType.FIXED_INCOME),
    ("درآمدثابت", FundType.FIXED_INCOME),
    ("مختلط", FundType.MIXED),
    ("کالا", FundType.COMMODITY),
    ("طلا", FundType.COMMODITY),
    ("ثابت", FundType.FIXED_INCOME),  # names ending in "-ثابت"
    ("سهام", FundType.EQUITY),
)
# Iranian fund names end with a type letter: "صندوق س.آوان ژرف آگاه-س".
# Verified against faraDesc on every fund that has both (docs/02, tests).
_NAME_SUFFIX = {
    "س": FundType.EQUITY,
    "ب": FundType.SECTOR,
    "د": FundType.FIXED_INCOME,
    "م": FundType.MIXED,
}
_SUFFIX_RE = re.compile(r"-\s*(\S)\s*$")


def _by_keyword(text: str) -> FundType | None:
    return next((t for kw, t in _KEYWORDS if kw in text), None)


def classify_fund(fara_desc: str | None, name: str | None = None, isin: str = "") -> FundType:
    """Fund type from the official description, falling back to the naming convention.

    1. ``IRTK`` ISINs are commodity funds.
    2. ``faraDesc`` (the official type) when present. "سهامی" alone is refined
       with the name, which often reveals index or sector funds.
    3. Otherwise (≈25% of funds have an empty ``faraDesc``) the type letter at
       the end of the name, then keywords in the name.
    """
    if isin.startswith("IRTK"):
        return FundType.COMMODITY
    desc, title = normalize_fa(fara_desc), normalize_fa(name)
    if desc:
        base = _by_keyword(desc) or FundType.OTHER
    elif (m := _SUFFIX_RE.search(title)) and m.group(1) in _NAME_SUFFIX:
        base = _NAME_SUFFIX[m.group(1)]
    else:
        return _by_keyword(title) or FundType.OTHER
    if base is FundType.EQUITY:
        refined = _by_keyword(title)
        if refined in (FundType.LEVERAGED, FundType.INDEX, FundType.SECTOR):
            return refined
    return base


def is_fund_unit(isin: str, sector: str) -> bool:
    return sector.strip() == FUND_SECTOR and isin.startswith("IRT")


def is_primary_board(isin: str) -> bool:
    return isin.endswith(PRIMARY_BOARD_SUFFIX)


def isin_stem(isin: str) -> str:
    """ISIN without the 4-character board suffix: IRT3SATF0001 → IRT3SATF."""
    return isin[:-4]


@dataclass(frozen=True, slots=True)
class FundRef:
    """The slice of reference data the per-minute pipeline needs."""

    ins_code: str
    symbol: str
    name: str
    isin: str
    fund_type: FundType
    units: int | None = None

    @property
    def stem(self) -> str:
        return isin_stem(self.isin)
