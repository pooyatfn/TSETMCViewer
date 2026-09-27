"""Tehran Stock Exchange trading calendar: weekends, official holidays, closures.

Three layers, most specific wins:

1. **Official holidays** — solar ones follow fixed Jalali dates every year; lunar
   (religious) ones move ~11 days a year and are listed per Jalali year from the
   officially published calendar.
2. **Extra closures** — configured by the operator (``MARKET_EXTRA_HOLIDAYS``)
   for one-off announcements.
3. **Observed** — what the market actually did, learned at runtime by the
   collector's session guard: a listed trading day on which TSETMC never shows a
   trade is an unannounced closure; a listed holiday on which it does trade is an
   error in our table. Observations override the lists.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from tsetmc_viewer.domain.jalali import from_jalali, to_jalali

log = logging.getLogger(__name__)

# Fixed Jalali dates, every year.
SOLAR_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "نوروز"),
    (1, 2, "نوروز"),
    (1, 3, "نوروز"),
    (1, 4, "نوروز"),
    (1, 12, "روز جمهوری اسلامی"),
    (1, 13, "روز طبیعت"),
    (3, 14, "رحلت امام خمینی"),
    (3, 15, "قیام ۱۵ خرداد"),
    (11, 22, "پیروزی انقلاب اسلامی"),
    (12, 29, "ملی شدن صنعت نفت"),
)

# Religious holidays by Jalali year, from the official calendar of that year.
# 1405: cross-checked between published calendars and a Hijri conversion; the
# session guard corrects any day that turns out different in practice.
LUNAR_HOLIDAYS: dict[int, tuple[tuple[int, int, str], ...]] = {
    1405: (
        (1, 1, "عید فطر"),
        (1, 2, "تعطیلی عید فطر"),
        (1, 25, "شهادت امام جعفر صادق"),
        (3, 6, "عید قربان"),
        (3, 14, "عید غدیر"),
        (4, 3, "تاسوعا"),
        (4, 4, "عاشورا"),
        (5, 13, "اربعین"),
        (5, 21, "رحلت پیامبر و شهادت امام حسن"),
        (5, 22, "شهادت امام رضا"),
        (5, 30, "شهادت امام حسن عسکری"),
        (6, 8, "میلاد پیامبر و امام جعفر صادق"),
        (8, 22, "شهادت حضرت فاطمه"),
        (10, 2, "ولادت امام علی"),
        (10, 16, "مبعث"),
        (11, 4, "نیمه شعبان"),
        (12, 9, "شهادت امام علی"),
        (12, 19, "عید فطر"),
        (12, 20, "تعطیلی عید فطر"),
    ),
}

Source = Literal["official", "extra", "observed"]


@dataclass(frozen=True, slots=True)
class DayStatus:
    day: date
    trading: bool
    reason: str | None  # holiday name / closure note; None on a plain trading day
    source: Source | Literal["weekday", "weekend"]


class HolidayCalendar:
    def __init__(
        self,
        trading_weekdays: Iterable[int],
        extra: Mapping[date, str] | None = None,
    ) -> None:
        self._weekdays = frozenset(trading_weekdays)
        self._extra = dict(extra or {})
        self._observed: dict[date, tuple[bool, str]] = {}
        self._warned_years: set[int] = set()
        self._official: dict[int, dict[date, str]] = {}

    # --- lists ------------------------------------------------------------------------
    def official(self, jalali_year: int) -> dict[date, str]:
        """Official holidays of a Jalali year (solar rules + that year's lunar table)."""
        if jalali_year in self._official:
            return self._official[jalali_year]
        days: dict[date, list[str]] = {}
        for month, day, name in (*SOLAR_HOLIDAYS, *LUNAR_HOLIDAYS.get(jalali_year, ())):
            days.setdefault(from_jalali(jalali_year, month, day), []).append(name)
        result = {d: " و ".join(dict.fromkeys(names)) for d, names in sorted(days.items())}
        self._official[jalali_year] = result
        return result

    def has_lunar_table(self, jalali_year: int) -> bool:
        return jalali_year in LUNAR_HOLIDAYS

    # --- runtime observations -------------------------------------------------------------
    def observe(self, day: date, *, trading: bool, note: str) -> None:
        self._observed[day] = (trading, note)

    def load_observed(self, rows: Iterable[tuple[date, bool, str]]) -> None:
        for day, trading, note in rows:
            self.observe(day, trading=trading, note=note)

    # --- queries ----------------------------------------------------------------------
    def status(self, day: date) -> DayStatus:
        if day in self._observed:
            trading, note = self._observed[day]
            return DayStatus(day, trading, None if trading else note, "observed")
        if day in self._extra:
            return DayStatus(day, False, self._extra[day], "extra")
        if day.weekday() not in self._weekdays:
            return DayStatus(day, False, None, "weekend")
        jy = to_jalali(day)[0]
        if not self.has_lunar_table(jy) and jy not in self._warned_years:
            self._warned_years.add(jy)
            log.warning(
                "no lunar holiday table for this year; relying on the session guard",
                extra={"jalali_year": jy},
            )
        name = self.official(jy).get(day)
        if name is not None:
            return DayStatus(day, False, name, "official")
        return DayStatus(day, True, None, "weekday")

    def is_trading_day(self, day: date) -> bool:
        return self.status(day).trading

    def holiday_name(self, day: date) -> str | None:
        """Name of the holiday/closure on a weekday that would otherwise trade."""
        s = self.status(day)
        return s.reason if not s.trading and s.source != "weekend" else None
