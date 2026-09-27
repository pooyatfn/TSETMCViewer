"""Gregorian ↔ Jalali (Solar Hijri) conversion.

The Iranian fiscal and market year starts on 1 Farvardin, so "year to date"
returns need the Gregorian date of Nowruz. The arithmetic algorithm below
(based on the 33-year cycle, as used by jdatetime/Borkowski-style converters)
is exact for 1178–1633 SH, far beyond anything this service stores.
"""

from __future__ import annotations

from datetime import date, timedelta

_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262,
           2324, 2394, 2456, 3178)  # fmt: skip


def _jal_cal(jy: int) -> tuple[int, int, int]:
    """(leap flag, Gregorian year, day of March of 1 Farvardin) for Jalali year ``jy``."""
    gy = jy + 621
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += (jump // 33) * 8 + (jump % 33) // 4
        jp = jm
    n = jy - jp
    leap_j += (n // 33) * 8 + ((n % 33) + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1
    leap_g = gy // 4 - ((gy // 100 + 1) * 3) // 4 - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + ((jump + 4) // 33) * 33
    leap = (((n + 1) % 33) - 1) % 4
    if leap == -1:
        leap = 4
    return leap, gy, march


def nowruz(jy: int) -> date:
    """Gregorian date of 1 Farvardin of Jalali year ``jy``."""
    _, gy, march = _jal_cal(jy)
    return date(gy, 3, march)


def to_jalali(d: date) -> tuple[int, int, int]:
    jy = d.year - 621
    start = nowruz(jy)
    if d < start:
        jy -= 1
        start = nowruz(jy)
    day = (d - start).days  # 0-based day of the Jalali year
    if day < 186:
        return jy, day // 31 + 1, day % 31 + 1
    day -= 186
    return jy, day // 30 + 7, day % 30 + 1


def from_jalali(jy: int, jm: int, jd: int) -> date:
    """Gregorian date of the Jalali date ``jy/jm/jd``."""
    if not (1 <= jm <= 12 and 1 <= jd <= (31 if jm <= 6 else 30)):
        raise ValueError(f"invalid Jalali date {jy}/{jm}/{jd}")
    offset = (jm - 1) * 31 + jd - 1 if jm <= 7 else 186 + (jm - 7) * 30 + jd - 1
    result = nowruz(jy) + timedelta(days=offset)
    if to_jalali(result) != (jy, jm, jd):  # e.g. 30 Esfand in a non-leap year
        raise ValueError(f"invalid Jalali date {jy}/{jm}/{jd}")
    return result


def jalali_year_start(d: date) -> date:
    """1 Farvardin of the Jalali year containing ``d``."""
    return nowruz(to_jalali(d)[0])


def format_jalali(d: date) -> str:
    y, m, day = to_jalali(d)
    return f"{y:04d}/{m:02d}/{day:02d}"
