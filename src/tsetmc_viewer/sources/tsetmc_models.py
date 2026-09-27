"""Typed views over TSETMC JSON payloads.

Field aliases map TSETMC's abbreviations to readable names; the mapping was
derived by cross-checking market-watch rows against ``GetClosingPriceInfo``
for the same instrument (documented in docs/02-data-sources.md). Unknown
fields are ignored so additive API changes do not break parsing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from tsetmc_viewer.domain.text import normalize_fa

TEHRAN = ZoneInfo("Asia/Tehran")


def _to_int(value: Any) -> int:
    """TSETMC sends integer quantities as floats (157502.0) and sometimes null."""
    if value is None or value == "":
        return 0
    return round(float(value))


Int = Annotated[int, BeforeValidator(_to_int)]
Text = Annotated[str, BeforeValidator(lambda v: normalize_fa(v) if isinstance(v, str) else "")]
Code = Annotated[str, BeforeValidator(lambda v: str(v).strip() if v is not None else "")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


def tehran_datetime(deven: int, heven: int) -> datetime | None:
    """TSETMC dates: ``deven`` = YYYYMMDD (Gregorian), ``heven`` = HHMMSS (may lose a leading 0)."""
    if deven <= 0:
        return None
    h, rem = divmod(heven, 10000)
    m, s = divmod(rem, 100)
    y, md = divmod(deven, 10000)
    mo, d = divmod(md, 100)
    try:
        return datetime(y, mo, d, h, m, s, tzinfo=TEHRAN)
    except ValueError:
        return None


# --- market watch -----------------------------------------------------------


class BestLimit(_Model):
    level: Int = Field(alias="n")
    bid_price: Int = Field(alias="pmd")
    bid_volume: Int = Field(alias="qmd")
    bid_orders: Int = Field(alias="zmd")
    ask_price: Int = Field(alias="pmo")
    ask_volume: Int = Field(alias="qmo")
    ask_orders: Int = Field(alias="zmo")


class MarketWatchRow(_Model):
    ins_code: Code = Field(alias="insCode")
    symbol: Text = Field(alias="lva")
    name: Text = Field(alias="lvc")
    isin: Code = Field(alias="insID")
    sector: Code = Field(alias="csv")
    last_price: Int = Field(alias="pdv")
    close_price: Int = Field(alias="pcl")
    open_price: Int = Field(alias="pf")
    low_price: Int = Field(alias="pmn")
    high_price: Int = Field(alias="pmx")
    prev_close: Int = Field(alias="py")
    volume: Int = Field(alias="qtj")
    value: Int = Field(alias="qtc")
    trade_count: Int = Field(alias="ztt")
    max_allowed: Int = Field(alias="pMax")
    min_allowed: Int = Field(alias="pMin")
    heven: Int = Field(alias="hEven")
    best_limits: list[BestLimit] = Field(default_factory=list, alias="blDs")

    @property
    def top(self) -> BestLimit | None:
        return next((b for b in self.best_limits if b.level == 1), None)


# --- client types (individual / institutional) -------------------------------


class ClientTypeRow(_Model):
    ins_code: Code = Field(alias="insCode")
    ind_buy_volume: Int = Field(alias="buy_I_Volume")
    inst_buy_volume: Int = Field(alias="buy_N_Volume")
    ind_buy_count: Int = Field(alias="buy_CountI")
    inst_buy_count: Int = Field(alias="buy_CountN")
    ind_sell_volume: Int = Field(alias="sell_I_Volume")
    inst_sell_volume: Int = Field(alias="sell_N_Volume")
    ind_sell_count: Int = Field(alias="sell_CountI")
    inst_sell_count: Int = Field(alias="sell_CountN")


# --- ETF NAV -------------------------------------------------------------------


class EtfNav(_Model):
    ins_code: Code = Field(alias="insCode")
    deven: Int = Field(alias="deven")
    heven: Int = Field(alias="hEven")
    redemption: Int = Field(alias="pRedTran")
    subscription: Int = Field(alias="pSubTran")

    @property
    def nav_at(self) -> datetime | None:
        return tehran_datetime(self.deven, self.heven)


class InstrumentState(_Model):
    """``closingPriceInfo.instrumentState``: the instrument's trading status."""

    code: Text = Field(alias="cEtaval")
    title: Text = Field(default="", alias="cEtavalTitle")
    under_supervision: Int = Field(default=0, alias="underSupervision")


# --- instrument info (daily) ---------------------------------------------------


class InstrumentInfo(_Model):
    ins_code: Code = Field(alias="insCode")
    symbol: Text = Field(alias="lVal18AFC")
    name: Text = Field(alias="lVal30")
    isin: Code = Field(alias="instrumentID")
    fund_desc: Text = Field(default="", alias="faraDesc")
    units: Int = Field(default=0, alias="etfIssuedUnit")
    units_deven: Int = Field(default=0, alias="etfUnitDeven")
    market: Text = Field(default="", alias="flowTitle")
    board: Text = Field(default="", alias="cgrValCotTitle")


class MarketOverview(_Model):
    index_value: float = Field(alias="indexLastValue")
    index_change: float = Field(alias="indexChange")
    eq_index_value: float = Field(alias="indexEqualWeightedLastValue")
    eq_index_change: float = Field(alias="indexEqualWeightedChange")
    market_value: float = Field(alias="marketValue")
    state: Code = Field(alias="marketState")
    deven: Int = Field(alias="marketActivityDEven")
    heven: Int = Field(alias="marketActivityHEven")


# --- envelope parsers -------------------------------------------------------------


class PayloadError(ValueError):
    """The payload did not have the expected envelope."""


def _envelope(payload: Any, key: str) -> Any:
    if not isinstance(payload, dict) or key not in payload:
        raise PayloadError(f"expected top-level key {key!r}")
    return payload[key]


def parse_market_watch(payload: Any) -> list[MarketWatchRow]:
    return [MarketWatchRow.model_validate(r) for r in _envelope(payload, "marketwatch")]


def parse_client_types(payload: Any) -> list[ClientTypeRow]:
    return [ClientTypeRow.model_validate(r) for r in _envelope(payload, "clientTypeAllDto")]


def parse_etf(payload: Any) -> EtfNav | None:
    body = _envelope(payload, "etf")
    return EtfNav.model_validate(body) if body else None


def parse_instrument_state(payload: Any) -> InstrumentState | None:
    body = _envelope(payload, "closingPriceInfo")
    state = body.get("instrumentState") if isinstance(body, dict) else None
    return InstrumentState.model_validate(state) if state else None


def parse_instrument_info(payload: Any) -> InstrumentInfo:
    return InstrumentInfo.model_validate(_envelope(payload, "instrumentInfo"))


def parse_market_overview(payload: Any) -> MarketOverview:
    return MarketOverview.model_validate(_envelope(payload, "marketOverview"))


# --- daily history (backfill) --------------------------------------------------------


class DailyPriceRow(_Model):
    ins_code: Code = Field(alias="insCode")
    deven: Int = Field(alias="dEven")
    open_price: Int = Field(alias="priceFirst")
    high_price: Int = Field(alias="priceMax")
    low_price: Int = Field(alias="priceMin")
    close_price: Int = Field(alias="pClosing")
    last_price: Int = Field(alias="pDrCotVal")
    prev_close: Int = Field(alias="priceYesterday")
    volume: Int = Field(alias="qTotTran5J")
    value: Int = Field(alias="qTotCap")
    trade_count: Int = Field(alias="zTotTran")


class ClientTypeDailyRow(_Model):
    """Official end-of-day individual/institutional flows, including rial values."""

    ins_code: Code = Field(alias="insCode")
    deven: Int = Field(alias="recDate")
    ind_buy_volume: Int = Field(alias="buy_I_Volume")
    inst_buy_volume: Int = Field(alias="buy_N_Volume")
    ind_sell_volume: Int = Field(alias="sell_I_Volume")
    inst_sell_volume: Int = Field(alias="sell_N_Volume")
    ind_buy_value: Int = Field(alias="buy_I_Value")
    inst_buy_value: Int = Field(alias="buy_N_Value")
    ind_sell_value: Int = Field(alias="sell_I_Value")
    inst_sell_value: Int = Field(alias="sell_N_Value")
    ind_buy_count: Int = Field(alias="buy_I_Count")
    inst_buy_count: Int = Field(alias="buy_N_Count")
    ind_sell_count: Int = Field(alias="sell_I_Count")
    inst_sell_count: Int = Field(alias="sell_N_Count")


class TradeRow(_Model):
    """One trade of today (``Trade/GetTrade``). Measured 1405/07/04: 2.3 MB for all funds."""

    n: Int = Field(alias="nTran")  # sequence number within the day
    heven: Int = Field(alias="hEven")  # HHMMSS, Tehran
    volume: Int = Field(alias="qTitTran")
    price: Int = Field(alias="pTran")
    canceled: Int = Field(default=0, alias="canceled")


def parse_trades(payload: Any) -> list[TradeRow]:
    return [TradeRow.model_validate(r) for r in _envelope(payload, "trade")]


class PriceHistoryRow(_Model):
    """One price-change event of a **past** day (``ClosingPrice/GetClosingPriceHistory``).

    Same fields as ``DailyPriceRow`` (it is the same underlying feed) plus ``hEven``:
    every field here is the running total *as of that moment*, not a per-event delta —
    confirmed 1405/07/05 against a real payload (envelope key ``closingPriceHistory``).
    """

    heven: Int = Field(alias="hEven")
    last_price: Int = Field(alias="pDrCotVal")
    volume: Int = Field(alias="qTotTran5J")
    value: Int = Field(alias="qTotCap")
    trade_count: Int = Field(alias="zTotTran")


def parse_price_history(payload: Any) -> list[PriceHistoryRow]:
    return [PriceHistoryRow.model_validate(r) for r in _envelope(payload, "closingPriceHistory")]


def parse_daily_prices(payload: Any) -> list[DailyPriceRow]:
    return [DailyPriceRow.model_validate(r) for r in _envelope(payload, "closingPriceDaily")]


def parse_client_type_history(payload: Any) -> list[ClientTypeDailyRow]:
    return [ClientTypeDailyRow.model_validate(r) for r in _envelope(payload, "clientType")]
