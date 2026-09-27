"""TSETMC (Tehran Securities Exchange Technology Management Co.) API client.

Only transport concerns live here: which URL to call and how. Response parsing
is a separate step (``tsetmc_viewer.sources.parsers``) so raw bytes can be
persisted first.

Endpoints are grouped by how the collector uses them:
- bulk, called every minute: market watch, client types for all instruments
- per instrument, called every minute for funds only: ETF NAV
- per instrument, called daily: instrument info, price history
"""

from __future__ import annotations

from typing import Any

import httpx

from tsetmc_viewer.config import HttpSettings
from tsetmc_viewer.sources.http import HttpSource, RawResponse

# TSETMC "paper types" – passing all of them returns every listed instrument.
_ALL_PAPER_TYPES = range(1, 10)


class TsetmcClient(HttpSource):
    source_name = "tsetmc"

    def __init__(
        self,
        base_url: str,
        settings: HttpSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url,
            settings,
            headers={"Referer": "https://www.tsetmc.com/", "Origin": "https://www.tsetmc.com"},
            transport=transport,
        )

    # --- bulk (every minute) -------------------------------------------------
    async def market_watch(self) -> RawResponse:
        params: dict[str, Any] = {
            "market": 0,
            "industrialGroup": "",
            "showTraded": "false",
            "withBestLimits": "true",
            "hEven": 0,
            "RefID": 0,
        }
        params |= {f"paperTypes[{i}]": p for i, p in enumerate(_ALL_PAPER_TYPES)}
        return await self.get("market_watch", "/ClosingPrice/GetMarketWatch", params=params)

    async def market_overview(self) -> RawResponse:
        return await self.get("market_overview", "/MarketData/GetMarketOverview/1")

    async def client_type_all(self) -> RawResponse:
        return await self.get("client_type_all", "/ClientType/GetClientTypeAll")

    # --- per instrument (every minute, funds only) ---------------------------
    async def etf(self, ins_code: str) -> RawResponse:
        return await self.get("etf", f"/Fund/GetETFByInsCode/{ins_code}", ins_code=ins_code)

    async def closing_price_info(self, ins_code: str) -> RawResponse:
        return await self.get(
            "closing_price_info", f"/ClosingPrice/GetClosingPriceInfo/{ins_code}", ins_code=ins_code
        )

    async def client_type(self, ins_code: str) -> RawResponse:
        return await self.get(
            "client_type", f"/ClientType/GetClientType/{ins_code}/1/0", ins_code=ins_code
        )

    async def best_limits(self, ins_code: str) -> RawResponse:
        return await self.get("best_limits", f"/BestLimits/{ins_code}", ins_code=ins_code)

    async def trades(self, ins_code: str) -> RawResponse:
        """Every trade of today; used once a day to rebuild minutes missed before start."""
        return await self.get("trades", f"/Trade/GetTrade/{ins_code}", ins_code=ins_code)

    async def price_history(self, ins_code: str, day: str) -> RawResponse:
        """Price/volume/value change events of a **past** ``day`` (``YYYYMMDD``, Gregorian).

        Used to rebuild minute data for sessions the collector never ran during
        (``pipeline.backfill.SessionBackfill``); unlike ``trades()`` this works for any
        day, not just today (probed 1405/07/05, docs/02-data-sources.md).
        """
        path = f"/ClosingPrice/GetClosingPriceHistory/{ins_code}/{day}"
        return await self.get("price_history", path, ins_code=ins_code)

    # --- reference / history (daily) -----------------------------------------
    async def instrument_info(self, ins_code: str) -> RawResponse:
        return await self.get(
            "instrument_info", f"/Instrument/GetInstrumentInfo/{ins_code}", ins_code=ins_code
        )

    async def daily_history(self, ins_code: str) -> RawResponse:
        return await self.get(
            "daily_history",
            f"/ClosingPrice/GetClosingPriceDailyList/{ins_code}/0",
            ins_code=ins_code,
        )

    async def client_type_history(self, ins_code: str) -> RawResponse:
        return await self.get(
            "client_type_history", f"/ClientType/GetClientTypeHistory/{ins_code}", ins_code=ins_code
        )

    async def search(self, query: str) -> RawResponse:
        return await self.get("search", f"/Instrument/GetInstrumentSearch/{query}")
