# ADR 0010 — High Availability: Collector Leadership and Multiple API Workers

<div class="adr-meta"><span>Status: Accepted; supersedes the "single instance" section in ADR 0004</span><span>Date: After day 7</span></div>

!!! abstract "Summary"
    Several collector instances run and elect a leader via a **lease in Redis**. Only the leader calls TSETMC, and if it dies, another instance takes over roughly a minute later (with a clean shutdown, in a few seconds). The API runs with several processes (workers), and a Redis lock makes the computation of each cache key single-flight across all of them. The design **favors availability over uniqueness**, because duplicate work is harmless in this system, but lost data is not.

## Context

- Intraday data is unrecoverable ([ADR 0003](0003-raw-first-ingestion.md)). If the one collector dies mid-session, data is lost until restart.
- Running two uncoordinated collectors doubles the load on TSETMC and increases the risk of being blocked ([ADR 0004](0004-scheduling.md)).
- A single API process uses one core. Day 6's single-flight only worked within one process ([ADR 0006](0006-caching.md#day-6-review-two-fixes-after-the-load-test)).

**Key domain property:** duplicate writes are harmless. Each row's key is `(ins_code, ts)`, and `ReplacingMergeTree` drops the duplicate. So "two leaders for a few seconds" only costs something, while "no leader at all" loses data.

## Decision

### Collector Leadership {#collector-leadership}

```text
Every 15 seconds:  if the lease is empty or mine → acquire or renew it (60s)   ← one atomic Lua script
Leader:            run the cycles
Standby:           retry every 15 seconds
Clean shutdown:    release the lease → the other instance becomes leader on its next attempt
```

| Decision | Reason |
|---|---|
| A lease with a TTL, not a permanent lock | A leader that dies without releasing (kill -9, power loss) doesn't hold the lock forever |
| "Acquire or renew" in a single Lua script | An instance whose lease has expired can't renew another instance's lease |
| Renewal in a task separate from the loop | The loop may sleep for 30 minutes (outside market hours); the lease must not expire during that time |
| **With no Redis, or on a Redis error, every instance is leader** | Availability over uniqueness: duplicate data is harmless, missing data is not. The `TsetmcSplitBrain` alert reports this state |
| Bootstrap only by the leader | Startup outside market hours ([ADR 0004](0004-scheduling.md#day-5-review-startup-outside-market-hours)) doesn't run twice |

In compose, the default is `COLLECTOR_REPLICAS=2`. Each instance has its own heartbeat (`standby` or `collecting`), and Prometheus discovers all of them via DNS.

### Multiple API Workers

- `api --workers N` (default 2 in compose). uvicorn creates the processes, and each process its own app.
- **Two-layer single-flight:** first an in-process future, then a short lease in Redis (`lock:{key}`, 10 seconds). A process that didn't get the lock polls the cache every 50ms. If the lock owner hasn't written a response by the end of the TTL (e.g. it died), the waiting process computes it itself. The lock may delay the response slightly, but it never loses it.
- **Metrics:** with multiple processes, `prometheus_client` runs in multiprocess mode (a shared directory, `/metrics` aggregates all of them). The directory is cleared on every startup.

## Rejected Options

| Option | Why not |
|---|---|
| **Leader election with etcd, Consul, or Kubernetes** | Another distributed service for a small problem. Redis is already in the stack |
| **Redlock across multiple Redis instances** | Redlock is for when correctness depends on uniqueness. It doesn't here, since duplication is harmless |
| **Sharding funds across collectors** | TSETMC's market watch returns the whole market in one response. Splitting the work doesn't reduce requests, it only increases them |
| **Both collectors fetching simultaneously and deduplicating** | Doubles the load on TSETMC and increases the risk of being blocked |

## Consequences

- ➕ A sudden death of the leader collector loses about a minute of data (60s TTL, plus up to 15s until the standby's next attempt). On `docker stop`, the lease is released immediately, and the standby becomes leader on its next attempt (up to 15s). In a real drill, this handover took 2 seconds ([Monitoring and Alerting](../11-monitoring.md#live-outage-drill)).
- ➕ The API uses all cores, and ClickHouse load is still independent of the number of users.
- ➖ Redis is required for coordination. Without it, the system works but without uniqueness.
- ⚠️ Services still run on a single host. If the host itself or ClickHouse goes down, the whole system goes down. Multi-host HA (replicated ClickHouse, Redis Sentinel) is out of scope for this project ([Limitations](../10-limitations.md)).
- ⚠️ Host clocks don't matter: the TTL is measured inside Redis itself.

## Review: ClickHouse's Own Failure

This ADR explicitly put a ClickHouse outage out of scope ("if the host itself or ClickHouse goes down, the whole system goes down"). [ADR 0011](0011-clickhouse-replication.md) closes part of this: an optional profile, two `ReplicatedMergeTree` replicas with one Keeper. The death of **one replica** no longer means a service outage. The death of **the host itself** still takes everything down together — both replicas and the Keeper are still on the same single machine; that part of this decision is left unchanged.
