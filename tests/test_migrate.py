from __future__ import annotations

import re
from typing import Any

import pytest

from tsetmc_viewer.storage.migrate import (
    Migration,
    MigrationError,
    clusterize,
    load_migrations,
    migrate,
    split_statements,
)


class FakeClickHouse:
    """Records DDL and emulates the schema_migrations table."""

    def __init__(self) -> None:
        self.commands: list[str] = []
        self.rows: list[tuple[int, str]] = []

    async def command(self, cmd: str) -> None:
        self.commands.append(cmd)
        if cmd.startswith("INSERT INTO schema_migrations"):
            values = cmd.split("VALUES (")[1].rstrip(")").split(", ")
            self.rows.append((int(values[0]), values[2].strip("'")))

    async def query(self, query: str) -> Any:
        return type("R", (), {"result_rows": list(self.rows)})()


def test_split_statements_ignores_comments_and_blank() -> None:
    sql = (
        "-- header; not a statement\nCREATE TABLE a (x UInt8);\n\n-- c\nCREATE TABLE b (y UInt8);\n"
    )
    assert split_statements(sql) == ["CREATE TABLE a (x UInt8)", "CREATE TABLE b (y UInt8)"]


def test_bundled_migrations_are_ordered_and_idempotent() -> None:
    migrations = load_migrations()
    assert [m.version for m in migrations] == sorted(m.version for m in migrations)
    for m in migrations:
        for stmt in m.statements():
            assert "IF NOT EXISTS" in stmt, f"{m.name}: non-idempotent statement"


async def test_migrate_applies_once() -> None:
    db = FakeClickHouse()
    m = Migration(1, "0001_x.sql", "CREATE TABLE IF NOT EXISTS t (x UInt8);")
    assert await migrate(db, [m]) == ["0001_x.sql"]
    assert await migrate(db, [m]) == []
    assert sum("CREATE TABLE IF NOT EXISTS t" in c for c in db.commands) == 1


def test_clusterize_is_a_no_op_when_no_cluster_is_set() -> None:
    sql = "CREATE TABLE IF NOT EXISTS t (x UInt8) ENGINE = ReplacingMergeTree(x) ORDER BY x"
    assert clusterize(sql, "") == sql


def test_clusterize_adds_on_cluster_and_replicated_engines() -> None:
    sql = clusterize(
        "CREATE TABLE IF NOT EXISTS t (x UInt8) ENGINE = ReplacingMergeTree(x) ORDER BY x",
        "tsetmc_cluster",
    )
    assert "IF NOT EXISTS t ON CLUSTER 'tsetmc_cluster'" in sql
    assert "ENGINE = ReplicatedReplacingMergeTree(" in sql
    assert "'/clickhouse/tables/{shard}/{database}/{table}', '{replica}', x" in sql


def test_clusterize_handles_bare_mergetree_and_alter() -> None:
    engine_only = clusterize("CREATE TABLE IF NOT EXISTS t (x UInt8) ENGINE = MergeTree", "c")
    assert (
        "ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/{database}/{table}', '{replica}')"
        in engine_only
    )

    view = clusterize("CREATE MATERIALIZED VIEW IF NOT EXISTS v TO t AS SELECT 1", "c")
    assert "IF NOT EXISTS v ON CLUSTER 'c' TO t AS" in view

    alter = clusterize("ALTER TABLE t ADD COLUMN IF NOT EXISTS y UInt8", "c")
    assert alter == "ALTER TABLE t ON CLUSTER 'c' ADD COLUMN IF NOT EXISTS y UInt8"


def test_clusterize_does_not_change_the_stored_checksum() -> None:
    """clusterize() only touches statements at execution time (ADR 0011): a migration's
    checksum is computed from the file text, so it must never see the clustered form."""
    m = Migration(1, "0001_x.sql", "CREATE TABLE IF NOT EXISTS t (x UInt8) ENGINE = MergeTree;")
    before = m.checksum
    for stmt in m.statements():
        clusterize(stmt, "tsetmc_cluster")  # exercised, result discarded
    assert m.checksum == before


def test_bundled_migrations_clusterize_cleanly() -> None:
    """Every real migration, run through clusterize(), must not leave a bare
    (non-Replicated) MergeTree-family engine or an un-clustered CREATE/ALTER."""
    for m in load_migrations():
        for stmt in m.statements():
            clustered = clusterize(stmt, "tsetmc_cluster")
            if re.match(r"CREATE (TABLE|MATERIALIZED VIEW)|ALTER TABLE", clustered):
                assert "ON CLUSTER 'tsetmc_cluster'" in clustered, f"{m.name}: {clustered[:80]}"
            if "ENGINE = " in stmt:
                assert "ENGINE = Replicated" in clustered, f"{m.name}: {clustered[:80]}"


async def test_migrate_rejects_edited_migration() -> None:
    db = FakeClickHouse()
    await migrate(db, [Migration(1, "0001_x.sql", "CREATE TABLE IF NOT EXISTS t (x UInt8);")])
    edited = Migration(1, "0001_x.sql", "CREATE TABLE IF NOT EXISTS t (x UInt16);")
    with pytest.raises(MigrationError):
        await migrate(db, [edited])


@pytest.mark.integration
async def test_migrations_apply_on_real_clickhouse(ch_client: Any) -> None:
    applied = await migrate(ch_client)
    assert applied == [m.name for m in load_migrations()]
    assert await migrate(ch_client) == []
    tables = {row[0] for row in (await ch_client.query("SHOW TABLES")).result_rows}
    assert {"raw_snapshots", "fund_ticks", "funds", "collection_runs"} <= tables


@pytest.mark.integration
@pytest.mark.parametrize("named_tuples", [0, 1])
async def test_eod_view_works_whatever_the_tuple_naming_default(
    ch_client: Any, named_tuples: int
) -> None:
    """Regression: 24.8.14 turned enable_named_columns_in_function_tuple off (24.8.4 had it
    on), and the fund_eod_mv key type then no longer matched the table and 0004 failed."""
    ch_client.set_client_setting("enable_named_columns_in_function_tuple", named_tuples)
    await migrate(ch_client)
    cols = (
        "ins_code, ts, ingested_at, close_price, value, nav_redemption, "
        "ind_buy_value, ind_sell_value"
    )
    await ch_client.command(
        f"INSERT INTO fund_ticks ({cols}) VALUES "
        "('F', '2026-09-26 12:29:00', '2026-09-26 12:29:05', 100, 10, 99, 50, 20),"
        "('F', '2026-09-26 12:30:00', '2026-09-26 12:30:05', 101, 20, 98, 70, 20),"
        "('F', '2026-09-26 12:30:00', '2026-09-26 12:31:00', 102, 30, 97, 90, 20)"
    )
    row = (
        await ch_client.query(
            "SELECT argMaxMerge(close_price), argMaxMerge(value), argMaxMerge(nav_redemption), "
            "argMaxMerge(ind_net_value) FROM fund_eod GROUP BY ins_code"
        )
    ).result_rows[0]
    assert row == (102, 30, 97, 70)  # latest ts, then latest ingest (the replayed row)
