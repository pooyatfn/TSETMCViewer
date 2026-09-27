"""Financial metrics (docs/05-financial-logic.md). Pure functions, no I/O.

Conventions
- Prices and values are integer Rials; ratios are plain floats (0.012 = 1.2%).
- A metric that cannot be computed meaningfully returns ``None`` rather than a
  misleading number (e.g. the NAV premium of leveraged funds).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import median, pstdev

from tsetmc_viewer.domain.funds import FundType


def pct_change(current: float | None, reference: float | None) -> float | None:
    if not current or not reference:
        return None
    return current / reference - 1


def nav_premium(price: int | None, nav: int | None, fund_type: FundType) -> float | None:
    """NAV premium ("bubble" / حباب) = price / redemption NAV − 1.

    Positive: buyers pay more than the fund's assets are worth per unit.
    Leveraged funds return ``None``: the NAV TSETMC publishes for them is not
    the NAV of the ordinary (traded) units, so every leveraged fund shows an
    artificial ≈ −18% "discount" (measured on 7 of 9 funds, docs/05).
    """
    if fund_type is FundType.LEVERAGED:
        return None
    return pct_change(price, nav)


def aum(nav: int | None, units: int | None) -> int | None:
    """Net assets ≈ redemption NAV × units issued."""
    if not nav or not units:
        return None
    return nav * units


def net_flow(buy_value: int, sell_value: int) -> int:
    """Rial money moving from one investor group into the fund (positive) or out."""
    return buy_value - sell_value


def per_capita(value: int, count: int) -> float | None:
    return value / count if count > 0 else None


def buyer_power(buy_value: int, buy_count: int, sell_value: int, sell_count: int) -> float | None:
    """Average individual buy ticket ÷ average individual sell ticket.

    > 1 means the average buyer is bigger than the average seller — commonly
    read by Iranian traders as "smart money" entering.
    """
    buy, sell = per_capita(buy_value, buy_count), per_capita(sell_value, sell_count)
    if buy is None or sell is None or sell == 0:
        return None
    return buy / sell


def turnover(value: int, net_assets: int | None) -> float | None:
    """Traded value as a share of the fund's net assets (liquidity)."""
    if not net_assets:
        return None
    return value / net_assets


def robust_center(values: list[float | None]) -> float | None:
    """Median of the defined values: one outlier fund must not move the market figure."""
    defined = [v for v in values if v is not None]
    return median(defined) if defined else None


def weighted_mean(pairs: Iterable[tuple[float | None, float | None]]) -> float | None:
    """Mean of values weighted by e.g. net assets; pairs with a missing side are skipped.

    Used for the *weighted* market premium: where the money is, rather than the median's
    "typical fund". Both are shown because they answer different questions.
    """
    total = weight = 0.0
    for value, w in pairs:
        if value is None or w is None or w <= 0:
            continue
        total += value * w
        weight += w
    return total / weight if weight else None


TRADING_DAYS_PER_YEAR = 252


def volatility(closes: Sequence[int | float]) -> float | None:
    """Annualised volatility from a series of daily closes, oldest first.

    Population stdev of daily percent-returns × √252 — the standard, if rough,
    way to make a same-scale risk number out of a short daily series. Needs at
    least 5 closing prices (4 returns); below that a single bad print would
    dominate the number, so ``None`` is returned instead of a misleading value.
    """
    prices = [p for p in closes if p]
    if len(prices) < 5:
        return None
    daily_returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices)) if prices[i - 1]]
    if len(daily_returns) < 4:
        return None
    return float(pstdev(daily_returns) * TRADING_DAYS_PER_YEAR**0.5)
