"""ClickHouse connection factory."""

from __future__ import annotations

from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from tsetmc_viewer.config import ClickHouseSettings
from tsetmc_viewer.storage.migrate import clusterize


def _params(s: ClickHouseSettings, database: str | None) -> dict[str, Any]:
    return {
        "host": s.host,
        "port": s.port,
        "username": s.user,
        "password": s.password.get_secret_value(),
        "database": database if database is not None else s.database,
    }


async def create_client(s: ClickHouseSettings, *, database: str | None = None) -> AsyncClient:
    return await clickhouse_connect.get_async_client(**_params(s, database))


async def ensure_database(s: ClickHouseSettings) -> None:
    client = await create_client(s, database="default")
    try:
        stmt = clusterize(f"CREATE DATABASE IF NOT EXISTS `{s.database}`", s.cluster)
        await client.command(stmt)
    finally:
        await client.close()
