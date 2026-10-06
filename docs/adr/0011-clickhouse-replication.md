# ADR 0011 — ClickHouse Replication: Two Replicas, One Keeper

<div class="adr-meta"><span>Status: Accepted; optional, complements ADR 0010</span><span>Date: After day 7</span></div>

!!! abstract "Summary"
    An optional compose profile (`ha-storage`) brings up two ClickHouse replicas using the **`ReplicatedMergeTree`** engine, coordinated through a single **ClickHouse Keeper**: every `INSERT` on one reaches the other too, on ClickHouse's own schedule. This profile runs **alongside** the default single-replica service, not in place of it, and is explicitly **not a substitute for multi-host**: both replicas and the Keeper are on the same single machine, so the death of that machine takes both down together. What you actually get is resilience against the death of **one container** or a disk failure on one replica, not against the death of the server.

## Context

- [ADR 0010](0010-high-availability.md) states explicitly: "services still run on a single host. If ClickHouse goes down, the whole system stops," and puts that out of scope. This ADR partially closes that same gap, at moderate cost.
- Unlike the collector (which [ADR 0010](0010-high-availability.md#collector-leadership) elects a leader for, via a lease in Redis) and the API (which runs several independent workers with a distributed single-flight), **ClickHouse is stateful**: you can't have "two independent replicas that each write separately," because their data would no longer be the same. Replication here has to live at the **table-engine level**.
- This project had a 7-day deadline, and real multi-host ClickHouse (a quorum-backed Keeper, replicas on separate machines) is several days of work on its own. This ADR's core question: "how much of the mechanism can be shown correctly, tested, and honestly, without claiming full HA?"

## Decision

### Why one shard, two replicas (not sharding)

The data isn't high-volume (432 funds, a few megabytes per minute), and queries run over the whole market at once (market map, full table). Sharding would have complicated queries for no benefit; what was needed was just **one backup copy of the same data**.

### Mechanism

```text
Keeper (one instance)  ←—— coordinates DDL and replication metadata ——→  clickhouse-0
                                                                          clickhouse-1
migrate runs once, on clickhouse-0:
  CREATE TABLE ... ON CLUSTER 'tsetmc_cluster' ENGINE = ReplicatedReplacingMergeTree(...)
  → Keeper runs the same DDL on clickhouse-1 too (distributed DDL queue)
Every INSERT on either replica → reaches the other (ReplicatedMergeTree's own mechanism, not a client-side re-write)
```

| Decision | Reason |
|---|---|
| Replication at the **table engine** level, not in code | `ReplicatedReplacingMergeTree`/`ReplicatedMergeTree`/`ReplicatedAggregatingMergeTree` do this with ClickHouse's own guarantees; writing it in Python would mean reproducing something the database already does correctly |
| Table paths with the built-in `{database}`/`{table}` macros plus config macros `{shard}`/`{replica}` | One path pattern for every table, without writing each table's name anywhere else; makes copy-paste mistakes or forgetting a table impossible |
| Rewriting to `Replicated*` only **at runtime** in `migrate()`, not in the SQL files | Migrations are "never edited after they've run," and checksums enforce that ([ADR 0005](0005-migrations.md)). If we changed the engine in the file itself, the file's checksum would change and existing installs would fail with an error |
| `CLICKHOUSE_CLUSTER` empty by default | The single-replica install (still the default) sees no change at all; the cluster is fully optional and opt-in |
| Keeper instead of a separate ZooKeeper | The ClickHouse binary already has `clickhouse keeper` built in; one fewer image, one fewer failure point to understand |
| A separate profile (`ha-storage`), not a replacement for the `clickhouse` service | The default single-replica service stays untouched; anyone who doesn't enable this profile sees nothing different in the "one command" experience |

### Switching to the replicas

Turning on this profile alone doesn't move the application's data — two independent databases come up side by side. To actually use the replicas:

```bash
docker compose --profile ha-storage up -d clickhouse-keeper clickhouse-0 clickhouse-1 migrate-ha
```

Then in `.env`: `CLICKHOUSE_HOST=clickhouse-0` and `CLICKHOUSE_CLUSTER=tsetmc_cluster`, and `docker compose up -d --force-recreate api collector` so they come up with the new settings. The default `clickhouse` service is no longer needed; keeping it running means an unused database sitting idle.

To verify replication is actually working:

```bash
# Write something on clickhouse-0; it should also appear on clickhouse-1 (a few seconds' delay is normal)
curl -u default:tsetmc 'http://127.0.0.1:8125/?query=SELECT count() FROM tsetmc.funds'
# Stop one replica; the app (on clickhouse-0) should keep working
docker compose stop clickhouse-1
```

## Rejected Options

| Option | Why not |
|---|---|
| **Not implementing this ADR, just periodic backups** | Backups don't protect against downtime, only against total data loss; the service would still be down until restore |
| **3 Keeper replicas for a real quorum** | Meaningless on a single host (if the host dies, all three die together); a real quorum needs separate hosts, which is out of scope for this project |
| **Sharding instead of replication** | The data isn't high-volume; sharding would only slow down and complicate market-wide queries |
| **A load balancer/proxy in front of the two replicas (e.g. chproxy)** | Needed for automatic failover, but adds one more service to maintain. For now, switching is manual via `CLICKHOUSE_HOST`; if this profile becomes the default, a proxy is the natural next step |
| **Rewriting the engine in the migration files themselves (instead of a runtime rewrite)** | Would invalidate the checksums of already-applied migrations ([ADR 0005](0005-migrations.md)) |

## Consequences

- ➕ The death of one ClickHouse replica no longer means a service outage; the other replica has the same data.
- ➕ `CLICKHOUSE_CLUSTER=""` by default means no existing install sees any behavior change; enabling it is fully opt-in.
- ➖ More code and config to maintain: three compose services, three XML files, one rewrite function in `migrate.py`.
- ⚠️ **This is not real HA.** Both replicas and the Keeper are on one host; the host's death takes all three down together. The honest label is "resilience against the death of one container or a disk failure on one replica," not "resilience against server failure" (which is the goal of [Operational Limitations](../10-limitations.md#operational-limitations)).
- ⚠️ The single-instance Keeper is itself a single point of failure for **coordination** (not for data: data lives on disk on both replicas). If the Keeper is down, replication and new DDL stop, but direct reads and writes on each replica continue.
- ⚠️ Without a proxy in front of the two replicas, switching to the other replica is manual (`CLICKHOUSE_HOST` in `.env`, then restarting `api`/`collector`).
- ⚠️ CI doesn't run this profile (neither the Keeper nor two replicas in the smoke-test setup); the correctness of the SQL rewrite is covered by a unit test on `clusterize()` (`tests/test_migrate.py`), not by a real cluster.
