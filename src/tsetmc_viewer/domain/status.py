"""Trading status of an instrument ("وضعیت نماد"), as TSETMC reports it.

``GetClosingPriceInfo`` carries ``instrumentState.cEtaval``: a one- or two-letter
code whose first letter says whether the instrument may be traded (A = مجاز,
I = ممنوع) and whose second letter qualifies it (S = متوقف, R = محفوظ,
G = مسدود). TSETMC also sends its own Persian title (``cEtavalTitle``); the panel
shows that title verbatim and uses ``kind`` only to decide how loud to be.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum


class StatusKind(StrEnum):
    OPEN = "open"  # A: trading normally
    SUSPENDED = "suspended"  # …S: halted (متوقف)
    RESERVED = "reserved"  # …R: reserved (محفوظ), usually before an announcement
    BLOCKED = "blocked"  # …G: blocked (مسدود)
    FORBIDDEN = "forbidden"  # I: not allowed to trade (ممنوع)
    UNKNOWN = "unknown"


def status_kind(code: str) -> StatusKind:
    code = code.strip().upper()
    if not code:
        return StatusKind.UNKNOWN
    qualifier = code[1:2]
    if qualifier == "S":
        return StatusKind.SUSPENDED
    if qualifier == "R":
        return StatusKind.RESERVED
    if qualifier == "G":
        return StatusKind.BLOCKED
    if code[0] == "I":
        return StatusKind.FORBIDDEN
    if code == "A":
        return StatusKind.OPEN
    return StatusKind.UNKNOWN


@dataclass(frozen=True, slots=True)
class FundState:
    """One observation of a fund's status. Field order == insert column order."""

    ts: datetime
    ins_code: str
    code: str
    title: str
    under_supervision: int
    ingested_at: datetime

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> list[object]:
        return [getattr(self, c) for c in self.columns()]
