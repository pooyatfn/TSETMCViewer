"""Fipiran (fund.fipiran.ir) client – the reference source for fund metadata.

TSETMC knows the *instrument* (price, volume, NAV); Fipiran knows the *fund*
(type, manager, inception, net assets, asset allocation). Called once per day.
"""

from __future__ import annotations

from tsetmc_viewer.sources.http import HttpSource, RawResponse


class FipiranClient(HttpSource):
    source_name = "fipiran"

    async def fund_compare(self) -> RawResponse:
        """All registered funds with type, manager, NAV, net assets and returns."""
        return await self.get("fund_compare", "/fund/fundcompare")
