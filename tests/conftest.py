from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from tsetmc_viewer.config import ClickHouseSettings, HttpSettings, MarketSettings


@pytest.fixture
def http_settings() -> HttpSettings:
    return HttpSettings(timeout_seconds=1, max_retries=2, backoff_base_seconds=0, max_concurrency=4)


@pytest.fixture
def market_settings() -> MarketSettings:
    return MarketSettings()


@pytest.fixture
async def ch_client() -> AsyncIterator[object]:
    """A throwaway ClickHouse database; skipped unless CLICKHOUSE_HOST is set."""
    if not os.environ.get("CLICKHOUSE_HOST"):
        pytest.skip("CLICKHOUSE_HOST not set")
    from tsetmc_viewer.storage.clickhouse import create_client

    settings = ClickHouseSettings(database=f"test_{uuid4().hex[:8]}")
    admin = await create_client(settings, database="default")
    await admin.command(f"CREATE DATABASE {settings.database}")
    client = await create_client(settings)
    try:
        yield client
    finally:
        await client.close()
        await admin.command(f"DROP DATABASE {settings.database}")
        await admin.close()
