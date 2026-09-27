"""Alert relay: Alertmanager webhook → Bale / Telegram / webhook, in Persian."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from tsetmc_viewer.alerting.relay import create_relay_app, format_message, runbook_link
from tsetmc_viewer.config import AlertSettings

FIRING: dict[str, Any] = {
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "TsetmcCollectorFailing", "severity": "critical",
                       "component": "collector"},
            "annotations": {
                "summary": "چرخه‌های دریافت پشت سر هم شکست می‌خورند",
                "description": "5 چرخه‌ی ناموفق پیاپی.",
                "runbook": "docs/11-monitoring.md#collector-failing",
            },
            "startsAt": "2026-09-26T06:41:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }
    ],
}  # fmt: skip
TOKEN = "123:SECRET"


def settings(**kw: Any) -> AlertSettings:
    return AlertSettings(docs_url="http://docs.local", **kw)


def test_runbook_anchor_becomes_a_docs_site_link() -> None:
    assert (
        runbook_link("docs/11-monitoring.md#collector-failing", "http://docs.local/")
        == "http://docs.local/11-monitoring/#collector-failing"
    )
    assert runbook_link("", "http://x") == ""


def test_message_is_persian_plain_text_with_tehran_time() -> None:
    text = format_message(FIRING, "http://docs.local")
    assert "[بحرانی] چرخه‌های دریافت پشت سر هم شکست می‌خورند" in text
    assert "دریافت داده · ساعت 10:11" in text  # 06:41 UTC = 10:11 Tehran
    assert "راهنما: http://docs.local/11-monitoring/#collector-failing" in text
    resolved = {**FIRING, "alerts": [{**FIRING["alerts"][0], "status": "resolved",
                                      "endsAt": "2026-09-26T06:50:00Z"}]}  # fmt: skip
    text = format_message(resolved, "http://docs.local")
    assert text.splitlines()[2].startswith("[رفع شد]")
    assert "راهنما" not in text


async def test_delivers_to_every_channel_without_parse_mode() -> None:
    s = settings(
        bale_token=SecretStr(TOKEN), bale_chat_id="42",
        telegram_token=SecretStr(TOKEN), telegram_chat_id="7",
        webhook_url="http://hooks.local/in",
    )  # fmt: skip
    with respx.mock(assert_all_called=True) as router:
        bale = router.post(f"https://tapi.bale.ai/bot{TOKEN}/sendMessage").respond(200)
        tg = router.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage").respond(200)
        hook = router.post("http://hooks.local/in").respond(204)
        async with httpx.AsyncClient() as client:
            transport = httpx.ASGITransport(app=create_relay_app(s, client))
            async with httpx.AsyncClient(transport=transport, base_url="http://relay") as http:
                resp = await http.post("/alertmanager", json=FIRING)
    assert resp.status_code == 200
    assert resp.json() == {"delivered": {"bale": "ok", "telegram": "ok", "webhook": "ok"}}
    body = json.loads(bale.calls.last.request.content)
    assert set(body) == {"chat_id", "text"}  # Bale documents no parse_mode
    assert body["chat_id"] == "42"
    assert json.loads(tg.calls.last.request.content)["chat_id"] == "7"
    assert json.loads(hook.calls.last.request.content) == FIRING


async def test_all_channels_failing_asks_alertmanager_to_retry_and_hides_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    s = settings(bale_token=SecretStr(TOKEN), bale_chat_id="42")
    with respx.mock as router, caplog.at_level(logging.ERROR):
        router.post(f"https://tapi.bale.ai/bot{TOKEN}/sendMessage").respond(500)
        async with httpx.AsyncClient() as client:
            transport = httpx.ASGITransport(app=create_relay_app(s, client))
            async with httpx.AsyncClient(transport=transport, base_url="http://relay") as http:
                resp = await http.post("/alertmanager", json=FIRING)
    assert resp.status_code == 502
    assert TOKEN not in caplog.text


async def test_no_channel_configured_only_logs() -> None:
    transport = httpx.ASGITransport(app=create_relay_app(settings()))
    async with httpx.AsyncClient(transport=transport, base_url="http://relay") as http:
        assert (await http.get("/health")).json() == {"status": "ok", "channels": []}
        resp = await http.post("/alertmanager", json=FIRING)
    assert resp.status_code == 200
    assert resp.json() == {"delivered": {}}
