from __future__ import annotations

import httpx
import pytest
import respx

from tsetmc_viewer.config import HttpSettings
from tsetmc_viewer.sources.http import SourceError
from tsetmc_viewer.sources.tsetmc import TsetmcClient

BASE = "https://cdn.tsetmc.com/api"


@respx.mock
async def test_retries_transient_status_then_succeeds(http_settings: HttpSettings) -> None:
    route = respx.get(f"{BASE}/ClientType/GetClientTypeAll").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"clientTypeAllDto": []})]
    )
    async with TsetmcClient(BASE, http_settings) as client:
        resp = await client.client_type_all()
    assert route.call_count == 2
    assert resp.ok
    assert resp.attempts == 2
    assert resp.json() == {"clientTypeAllDto": []}


@respx.mock
async def test_does_not_retry_client_errors(http_settings: HttpSettings) -> None:
    route = respx.get(f"{BASE}/BestLimits/123").mock(return_value=httpx.Response(404))
    async with TsetmcClient(BASE, http_settings) as client:
        resp = await client.best_limits("123")
    assert route.call_count == 1
    assert resp.status_code == 404
    assert resp.ins_code == "123"


@respx.mock
async def test_raises_after_exhausting_retries(http_settings: HttpSettings) -> None:
    route = respx.get(f"{BASE}/Fund/GetETFByInsCode/1").mock(
        side_effect=httpx.ConnectTimeout("boom")
    )
    async with TsetmcClient(BASE, http_settings) as client:
        with pytest.raises(SourceError):
            await client.etf("1")
    assert route.call_count == http_settings.max_retries + 1


@respx.mock
async def test_last_retryable_response_is_returned_not_raised(http_settings: HttpSettings) -> None:
    respx.get(f"{BASE}/ClientType/GetClientTypeAll").mock(return_value=httpx.Response(502))
    async with TsetmcClient(BASE, http_settings) as client:
        resp = await client.client_type_all()
    assert resp.status_code == 502
    assert not resp.ok


@respx.mock
async def test_market_watch_requests_all_paper_types(http_settings: HttpSettings) -> None:
    route = respx.get(f"{BASE}/ClosingPrice/GetMarketWatch").mock(
        return_value=httpx.Response(200, json={"marketwatch": []})
    )
    async with TsetmcClient(BASE, http_settings) as client:
        await client.market_watch()
    params = route.calls.last.request.url.params
    assert params["paperTypes[0]"] == "1"
    assert params["withBestLimits"] == "true"
    assert route.calls.last.request.headers["Referer"].startswith("https://www.tsetmc.com")
