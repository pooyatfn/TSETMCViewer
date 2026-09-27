"""Minimal forward-only migrator for ClickHouse.

Why not Alembic? Alembic is built around SQLAlchemy and transactional DDL;
ClickHouse has neither. Plain numbered ``.sql`` files, applied in order and
recorded with a checksum, are easier to read and review.

Rules
- Files are named ``NNNN_description.sql`` and never edited after release
  (a checksum mismatch aborts the run).
- Every statement must be idempotent, since ClickHouse cannot roll back a
  partially applied file.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from importlib import resources
from typing import Protocol

log = logging.getLogger(__name__)

_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_LINE_COMMENT = re.compile(r"--[^\n]*")

# ADR 0011: turn one node's DDL into cluster-wide DDL. Applied at execution
# time only (never to the file on disk), so a migration's stored checksum is
# the same whether or not clustering is on.
_CREATE = re.compile(
    r"(CREATE\s+(?:TABLE|MATERIALIZED VIEW|DATABASE)\s+IF NOT EXISTS\s+\S+)", re.IGNORECASE
)
_ALTER = re.compile(r"(ALTER TABLE\s+\S+)", re.IGNORECASE)
_ENGINE = re.compile(
    r"ENGINE\s*=\s*(MergeTree|ReplacingMergeTree|AggregatingMergeTree)(\([^)]*\))?"
)


class Executor(Protocol):
    async def command(self, cmd: str) -> object: ...
    async def query(self, query: str) -> object: ...


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()

    def statements(self) -> list[str]:
        return split_statements(self.sql)


class MigrationError(RuntimeError):
    pass


def split_statements(sql: str) -> list[str]:
    """Split a script on ``;``. Comments are stripped; string literals must not contain ``;``."""
    body = _LINE_COMMENT.sub("", sql)
    return [s.strip() for s in body.split(";") if s.strip()]


def _replicate_engine(match: re.Match[str]) -> str:
    base, args = match.group(1), match.group(2)
    inner = args[1:-1].strip() if args else ""
    # {shard}/{replica} are macros (config.d); {database}/{table} are ClickHouse
    # built-ins, so the same template works for every table without naming it.
    path_args = "'/clickhouse/tables/{shard}/{database}/{table}', '{replica}'"
    if inner:
        path_args += f", {inner}"
    return f"ENGINE = Replicated{base}({path_args})"


def clusterize(sql: str, cluster: str) -> str:
    """Rewrite one statement for a replicated deployment (ADR 0011).

    Adds ``ON CLUSTER`` to every CREATE/ALTER and swaps the MergeTree-family
    engines this project uses for their Replicated* form. A no-op when
    ``cluster`` is empty — the default, single-node deployment unchanged.
    """
    if not cluster:
        return sql
    sql = _CREATE.sub(rf"\1 ON CLUSTER '{cluster}'", sql)
    sql = _ALTER.sub(rf"\1 ON CLUSTER '{cluster}'", sql)
    return _ENGINE.sub(_replicate_engine, sql)


def load_migrations() -> list[Migration]:
    folder = resources.files("tsetmc_viewer.storage") / "migrations"
    found: list[Migration] = []
    for entry in folder.iterdir():
        match = _NAME.match(entry.name)
        if match:
            found.append(Migration(int(match.group(1)), entry.name, entry.read_text("utf-8")))
    found.sort(key=lambda m: m.version)
    versions = [m.version for m in found]
    if len(set(versions)) != len(versions):
        raise MigrationError(f"duplicate migration versions: {versions}")
    return found


_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migrations
(
    version    UInt32,
    name       String,
    checksum   String,
    applied_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
ORDER BY version
"""


async def applied_migrations(client: Executor) -> dict[int, str]:
    result = await client.query("SELECT version, checksum FROM schema_migrations FINAL")
    rows = getattr(result, "result_rows", [])
    return {int(v): str(c) for v, c in rows}


async def migrate(
    client: Executor, migrations: list[Migration] | None = None, *, cluster: str = ""
) -> list[str]:
    """Apply pending migrations; return the names applied in this call.

    ``cluster`` (ADR 0011) makes every statement ``ON CLUSTER`` and every table
    Replicated; empty (the default) runs exactly as on a single node.
    """
    await client.command(clusterize(_BOOKKEEPING, cluster))
    done = await applied_migrations(client)
    applied: list[str] = []
    for m in migrations if migrations is not None else load_migrations():
        if m.version in done:
            if done[m.version] != m.checksum:
                raise MigrationError(f"{m.name} was modified after being applied")
            continue
        log.info("applying migration", extra={"migration": m.name})
        for stmt in m.statements():
            await client.command(clusterize(stmt, cluster))
        await client.command(
            "INSERT INTO schema_migrations (version, name, checksum) "
            f"VALUES ({m.version}, '{m.name}', '{m.checksum}')"
        )
        applied.append(m.name)
    return applied
