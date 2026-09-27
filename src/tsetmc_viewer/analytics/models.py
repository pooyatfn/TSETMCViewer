"""Response models of the analytics API. They double as the API contract (OpenAPI)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from tsetmc_viewer.domain.funds import FundType
from tsetmc_viewer.domain.status import StatusKind


class FundSnapshot(BaseModel):
    ins_code: str
    symbol: str
    name: str
    fund_type: FundType
    fund_type_fa: str
    ts: datetime
    last_price: int
    close_price: int
    prev_close: int
    change: float | None = Field(description="close / previous close − 1")
    nav: int | None = Field(description="Redemption NAV per unit (Rial)")
    nav_at: datetime | None
    premium: float | None = Field(description="price / NAV − 1; null for leveraged funds")
    units: int | None
    aum: int | None = Field(description="Net assets ≈ NAV × units (Rial)")
    share_of_aum: float | None
    value: int
    volume: int
    trade_count: int
    block_value: int
    ind_net_flow: int = Field(description="Individual buy value − sell value (Rial, estimated)")
    inst_net_flow: int
    buyer_power: float | None
    turnover: float | None = Field(description="Traded value / net assets")
    quality_flags: list[str]
    status_kind: StatusKind = Field(
        default=StatusKind.UNKNOWN, description="open, suspended, reserved, blocked, forbidden"
    )
    status_title: str | None = Field(default=None, description="TSETMC's own Persian title")
    status_at: datetime | None = Field(default=None, description="When it was last checked")
    under_supervision: bool = False


class Overview(BaseModel):
    session_date: date
    session_date_fa: str
    last_update: datetime | None
    is_live: bool
    funds: int
    total_aum: int
    total_value: int
    ind_net_flow: int
    median_premium: float | None
    weighted_premium: float | None = Field(
        description="Premium weighted by net assets (leveraged funds excluded)"
    )
    at_premium: int
    at_discount: int
    advancers: int
    decliners: int
    unchanged: int
    index_value: float | None
    index_change: float | None  # fraction of the previous close (points / prev)
    completeness: float | None
    not_trading: int = Field(
        default=0, description="Funds whose status is not «مجاز» (suspended, reserved, …)"
    )
    holiday_today: str | None = Field(
        description="Why the market is shut today (official holiday or observed closure)"
    )


class PremiumPoint(BaseModel):
    """Market-wide NAV premium at one moment: median fund and net-assets-weighted."""

    at: datetime | date
    at_fa: str = Field(description="Jalali date of the point (YYYY/MM/DD)")
    median: float | None
    weighted: float | None
    funds: int


class CalendarDay(BaseModel):
    day: date
    day_fa: str
    trading: bool
    reason: str | None
    source: str


class SessionInfo(BaseModel):
    day: date
    day_fa: str
    has_intraday: bool = Field(description="Minute-by-minute ticks exist for this day")


class MarketFlowPoint(BaseModel):
    ts: datetime
    ind_net_flow: int = Field(description="Cumulative for the session, all equity funds")
    value: int
    index_value: float | None


class FundIntradayPoint(BaseModel):
    ts: datetime
    last_price: int
    close_price: int
    nav: int | None
    premium: float | None
    ind_net_flow: int | None  # None on backfilled minutes: trades carry no client type
    volume: int
    quality_flags: list[str]
    # Rebuilt from today's trades because the collector started late (ADR 0012):
    # price and volume only, no NAV, premium or flows.
    backfilled: bool = False


class DailyFlow(BaseModel):
    trade_date: date
    trade_date_fa: str
    fund_type: FundType
    ind_net_flow: int
    value: int
    estimated: bool = Field(description="True for today's live estimate, False for official")


class FundRisk(BaseModel):
    """One point of the risk/return chart: how bumpy the ride was vs. what it paid."""

    ins_code: str
    symbol: str
    fund_type: FundType
    volatility: float | None = Field(description="Annualised stdev of daily returns, this window")
    period_return: float | None = Field(description="Price return over the same window")
    aum: int | None


class FundReturns(BaseModel):
    ins_code: str
    symbol: str
    fund_type: FundType
    r_1d: float | None
    r_1w: float | None
    r_1m: float | None
    r_3m: float | None
    r_ytd: float | None


class DailyBar(BaseModel):
    trade_date: date
    trade_date_fa: str
    close_price: int
    value: int
    ind_net_flow: int


class FundDetail(BaseModel):
    snapshot: FundSnapshot
    returns: FundReturns | None
    history: list[DailyBar]
