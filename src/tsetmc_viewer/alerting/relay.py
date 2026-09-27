"""Alert relay: Alertmanager webhook → Bale / Telegram / any webhook (docs/11-monitoring.md).

Why a relay instead of Alertmanager's own receivers:

- **Bale works inside Iran**, Telegram usually does not. Bale's bot API is
  Telegram-compatible but documents no ``parse_mode``; Alertmanager's Telegram
  receiver always sends one. The relay sends plain text, which both accept.
- **Secrets stay in ``.env``.** Alertmanager cannot read environment variables in its
  config file; the relay reads ``ALERT_*`` settings like every other service.
- **Messages in Persian**, built from the rules' annotations, with a link to the runbook.

Delivery is best effort per channel. The relay answers 5xx only if *every* configured
channel failed, so Alertmanager retries without duplicating already-delivered messages.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from tsetmc_viewer import telemetry
from tsetmc_viewer.config import AlertSettings

log = logging.getLogger(__name__)
TEHRAN = ZoneInfo("Asia/Tehran")

SEVERITY_FA = {"critical": "بحرانی", "warning": "هشدار", "info": "اطلاع"}
COMPONENT_FA = {"collector": "دریافت داده", "api": "API", "database": "پایگاه داده"}


def runbook_link(runbook: str, docs_url: str) -> str:
    """``docs/11-monitoring.md#x`` → ``{docs_url}/11-monitoring/#x`` (MkDocs URL)."""
    if not runbook:
        return ""
    path, _, anchor = runbook.partition("#")
    page = path.removeprefix("docs/").removesuffix(".md")
    return f"{docs_url.rstrip('/')}/{page}/" + (f"#{anchor}" if anchor else "")


def _when(iso: str) -> str:
    try:
        return (
            datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TEHRAN).strftime("%H:%M")
        )
    except ValueError:
        return ""


def format_message(payload: dict[str, Any], docs_url: str) -> str:
    """One plain-text message for one Alertmanager notification (a group of alerts)."""
    blocks: list[str] = []
    for alert in payload.get("alerts", []):
        labels, notes = alert.get("labels", {}), alert.get("annotations", {})
        resolved = alert.get("status") == "resolved"
        head = (
            "[رفع شد]" if resolved else f"[{SEVERITY_FA.get(labels.get('severity', ''), 'هشدار')}]"
        )
        lines = [f"{head} {notes.get('summary') or labels.get('alertname', '')}"]
        if not resolved and notes.get("description"):
            lines.append(notes["description"])
        part = COMPONENT_FA.get(labels.get("component", ""), labels.get("component", ""))
        since = _when(alert.get("endsAt" if resolved else "startsAt", ""))
        meta = " · ".join(x for x in (part, f"ساعت {since}" if since else "") if x)
        if meta:
            lines.append(meta)
        if not resolved and (link := runbook_link(notes.get("runbook", ""), docs_url)):
            lines.append(f"راهنما: {link}")
        blocks.append("\n".join(lines))
    return "TSETMCViewer\n\n" + "\n\n".join(blocks)


class Relay:
    def __init__(self, settings: AlertSettings, client: httpx.AsyncClient) -> None:
        self._s = settings
        self._client = client

    def channels(self) -> list[str]:
        s = self._s
        out = []
        if s.bale_token.get_secret_value() and s.bale_chat_id:
            out.append("bale")
        if s.telegram_token.get_secret_value() and s.telegram_chat_id:
            out.append("telegram")
        if s.webhook_url:
            out.append("webhook")
        return out

    async def _send(self, channel: str, payload: dict[str, Any], text: str) -> None:
        s = self._s
        if channel == "webhook":
            resp = await self._client.post(s.webhook_url, json=payload)
        else:
            api, token, chat = (
                (s.bale_api, s.bale_token, s.bale_chat_id)
                if channel == "bale"
                else (s.telegram_api, s.telegram_token, s.telegram_chat_id)
            )
            url = f"{api.rstrip('/')}/bot{token.get_secret_value()}/sendMessage"
            resp = await self._client.post(url, json={"chat_id": chat, "text": text})
        resp.raise_for_status()

    async def deliver(self, payload: dict[str, Any]) -> dict[str, str]:
        text = format_message(payload, self._s.docs_url)
        log.warning(
            "alert notification",
            extra={"status": payload.get("status"), "alerts": len(payload.get("alerts", []))},
        )
        results: dict[str, str] = {}
        for channel in self.channels():
            try:
                await self._send(channel, payload, text)
                results[channel] = "ok"
            except httpx.HTTPError as exc:
                # Never log the URL: for Bale/Telegram it contains the bot token.
                results[channel] = "error"
                log.error(
                    "alert delivery failed", extra={"channel": channel, "error": type(exc).__name__}
                )
            telemetry.ALERTS_RELAYED.labels(channel, results[channel]).inc()
        if not results:
            telemetry.ALERTS_RELAYED.labels("log", "ok").inc()
        return results


def create_relay_app(settings: AlertSettings, client: httpx.AsyncClient | None = None) -> FastAPI:
    app = FastAPI(title="TSETMCViewer alert relay", docs_url=None, redoc_url=None)
    relay = Relay(settings, client or httpx.AsyncClient(timeout=10))
    log.info("alert relay ready", extra={"channels": relay.channels() or ["log only"]})

    @app.post("/alertmanager")
    async def alertmanager(request: Request) -> JSONResponse:
        results = await relay.deliver(await request.json())
        failed_everywhere = bool(results) and all(r == "error" for r in results.values())
        return JSONResponse({"delivered": results}, status_code=502 if failed_everywhere else 200)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "channels": relay.channels()}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        body, content_type = telemetry.render()
        return Response(content=body, media_type=content_type)

    return app
