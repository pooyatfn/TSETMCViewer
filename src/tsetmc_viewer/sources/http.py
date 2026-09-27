"""A small, resilient async HTTP layer shared by all data sources.

Design notes
- Every call returns a :class:`RawResponse` (bytes + metadata), never a parsed
  object. Raw payloads are stored before parsing so any ingestion can be
  replayed after a parser fix.
- Retries use exponential backoff with full jitter on transient failures only
  (timeouts, connection errors, 429, 5xx). 4xx errors are returned, not retried.
- A semaphore caps in-flight requests so a 1-minute fan-out over ~150 funds does
  not trip the provider's rate limiting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from zoneinfo import ZoneInfo

import httpx

from tsetmc_viewer import telemetry
from tsetmc_viewer.config import HttpSettings

log = logging.getLogger(__name__)

TEHRAN = ZoneInfo("Asia/Tehran")
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


class SourceError(Exception):
    """Raised when a request fails after all retries."""


@dataclass(frozen=True, slots=True)
class RawResponse:
    source: str
    endpoint: str
    url: str
    status_code: int
    payload: bytes
    fetched_at: datetime
    latency_ms: int
    ins_code: str = ""
    attempts: int = 1
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return json.loads(self.payload)


class HttpSource:
    """Base class for a data provider reachable over HTTP(S)."""

    source_name: str = "http"

    def __init__(
        self,
        base_url: str,
        settings: HttpSettings,
        *,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={**BROWSER_HEADERS, **(headers or {})},
            timeout=settings.timeout_seconds,
            transport=transport,
            follow_redirects=True,
            http2=False,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _observe(self, endpoint: str, started: float) -> float:
        elapsed = time.perf_counter() - started
        telemetry.SOURCE_SECONDS.labels(self.source_name, endpoint).observe(elapsed)
        return elapsed

    def _backoff(self, attempt: int) -> float:
        # Full jitter: uniform(0, base * 2^attempt). See AWS architecture blog.
        return random.uniform(0, self._settings.backoff_base_seconds * 2**attempt)

    async def get(
        self,
        endpoint: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        ins_code: str = "",
    ) -> RawResponse:
        last_error: Exception | None = None
        attempts = self._settings.max_retries + 1
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                async with self._semaphore:
                    resp = await self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self._observe(endpoint, started)
                last_error = exc
                log.warning(
                    "request failed",
                    extra={"endpoint": endpoint, "attempt": attempt + 1, "error": repr(exc)},
                )
            else:
                latency = int(self._observe(endpoint, started) * 1000)
                if resp.status_code not in RETRYABLE_STATUS or attempt == attempts - 1:
                    outcome = "ok" if resp.is_success else f"http_{resp.status_code // 100}xx"
                    telemetry.SOURCE_REQUESTS.labels(self.source_name, endpoint, outcome).inc()
                    return RawResponse(
                        source=self.source_name,
                        endpoint=endpoint,
                        url=str(resp.request.url),
                        status_code=resp.status_code,
                        payload=resp.content,
                        fetched_at=datetime.now(TEHRAN),
                        latency_ms=latency,
                        ins_code=ins_code,
                        attempts=attempt + 1,
                    )
                last_error = SourceError(f"HTTP {resp.status_code}")
            if attempt < attempts - 1:
                telemetry.SOURCE_RETRIES.labels(self.source_name, endpoint).inc()
                await asyncio.sleep(self._backoff(attempt))
        telemetry.SOURCE_REQUESTS.labels(self.source_name, endpoint, "error").inc()
        raise SourceError(f"{self.source_name}:{endpoint} failed after {attempts} attempts") from (
            last_error
        )
