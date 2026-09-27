"""Persian text normalisation.

TSETMC mixes Arabic and Persian code points for the same letters (``ي``/``ی``,
``ك``/``ک``), so "سهامي" and "سهامی" are different strings. Every piece of
text we compare or store goes through :func:`normalize_fa`.
"""

from __future__ import annotations

import re

_TRANSLATE = str.maketrans(
    {
        "ي": "ی",  # ARABIC LETTER YEH → FARSI YEH
        "ى": "ی",  # ALEF MAKSURA → FARSI YEH
        "ك": "ک",  # ARABIC LETTER KAF → KEHEH
        "ة": "ه",
        "‏": "",  # RLM
        "‎": "",  # LRM
    }
)
_SPACES = re.compile(r"[ \t ]+")
_ZWNJ_RUN = re.compile(r"‌{2,}")


def normalize_fa(text: str | None) -> str:
    if not text:
        return ""
    text = text.translate(_TRANSLATE)
    text = _ZWNJ_RUN.sub("‌", text)
    return _SPACES.sub(" ", text).strip()
