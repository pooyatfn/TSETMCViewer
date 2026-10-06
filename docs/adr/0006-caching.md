# ADR 0006 — Caching Strategy

<div class="adr-meta"><span>Status: Accepted, revised on Day 4</span><span>Date: Day 1</span><span>Implementation: Day 2 and Day 4</span></div>

!!! abstract "Summary"
    Data only changes **once a minute**. So any response can be cached until the next tick, provided invalidation is tied to the **tick event**, not a guessed TTL. Caching happens across six layers, two in the collector and four in the read path.

## Context

Two independent pressures make caching necessary:

<div class="grid cards two" markdown>

-   :material-download-network-outline: __Source side: TSETMC is slow__

    ---

    The market watch is 3.5 MB of data for 3,800 symbols, while most symbols don't change within a minute. Symbol info and fund type are fixed throughout the day but get re-read for no reason. Every extra request also raises the risk of being blocked.

-   :material-monitor-dashboard: __Panel side: many users, one piece of data__

    ---

    Ten users with the panel open each send the same aggregate queries every few seconds, while the answer doesn't change until the next minute.

</div>

**Key domain property:** data changes **discretely and predictably**. Until tick N+1, the response for any query about tick N is final and immutable. This makes cache invalidation — usually the hardest part of caching — simple.

## Decision

<figure class="diagram">
<img src="../assets/diagrams/caching.svg" alt="Caching layers">
<figcaption>Six caching layers. The orange line is the "tick N" event path that implicitly invalidates caches.</figcaption>
</figure>

| # | Layer | What | Key / invalidation | Savings |
|:-:|---|---|---|---|
| ① | In-memory reference cache in the collector | Fund list, symbol info | Once a day, before market open | About 120 requests per minute |
| ② | ~~Last-watch state~~ | ~~Fetch only deltas~~ | **Rejected after measurement** (see below) | — |
|  | Conditional NAV | NAV computation time per fund | If `hEven` hasn't changed, the previous value is still valid | Fewer duplicate stores |
| ③ | Materialized Views | Daily and intraday aggregates | Updated on insert | Queries over thousands of rows, not millions |
| ④ | Redis (cache-aside) | JSON response per endpoint | `api:{route}:{hash(params)}:{tick}` with a 120-second TTL | ClickHouse is queried once per tick, not once per user |
| ⑤ | HTTP cache | Response in the browser or proxy | `ETag = tick`, `max-age` = seconds remaining until next tick | 304 responses with no body |
| ⑥ | SSE push | Announcing a new tick to the panel | Redis pub/sub channel | Eliminates polling |

### Why is the tick number inside the key?

Rather than deleting keys after every write (which is error-prone and race-condition-prone), **the version is part of the key**. When the collector announces tick N+1, the API starts building `…:N+1` keys from that point on. Old keys are simply never read again, and their TTL cleans them up. This pattern is called *key-based expiration* or *generational caching*.

```python title="Cache-aside pattern with tick version (sketch)"
async def cached(route: str, params: dict, compute: Callable[[], Awaitable[bytes]]) -> bytes:
    tick = await redis.get("tsetmc:tick")  # last committed tick
    key = f"api:{route}:{stable_hash(params)}:{tick}"
    if (hit := await redis.get(key)) is not None:
        return hit
    body = await compute()  # ClickHouse query
    await redis.set(key, body, ex=120)
    return body
```

!!! warning "Order matters: commit first, then announce the tick"
    The collector only publishes the tick **after** the `fund_ticks` insert finishes successfully. If the order were reversed, the API might cache an incomplete response for tick N under key N, and that incomplete response would be served until the next tick.

## Rejected Options

| Option | Why not |
|---|---|
| **No cache** | Works with one user, but with ten users ClickHouse runs ten times the duplicate queries. |
| **In-process cache (`lru_cache` or dict) in the API** | With multiple uvicorn workers, each process has its own separate cache and there's no pub/sub between processes. Suitable for the reference cache **in the collector** (layer ①), but not for the API. |
| **Fixed TTL only (e.g., 60 seconds)** | Not aligned with the tick. Might show stale data for up to 59 seconds, or expire earlier than necessary. |
| **ClickHouse's built-in query cache** | Simple, and enabled as a complement, but it's at the query level, doesn't cache serialized JSON, and has no pub/sub. |
| **CDN / Varnish** | Too much infrastructure for an internal service. The HTTP cache (⑤) gives the same benefit in the browser. |

## Consequences

- ➕ Load on TSETMC and ClickHouse becomes independent of the number of users.
- ➕ The panel is "live" (SSE), with no polling.
- ➖ One more service (Redis) in the compose file. In exchange, this same service also provides the event channel.
- ➖ If Redis is unavailable, the API must work without caching (fail-open): the cache error is logged and ClickHouse is queried directly.

## Day 4 Review: Layer ② Rejected After Measurement

The initial assumption was that a full watch takes 15 seconds. A second measurement with `scripts/probe_delta.py` (2 Mehr 1405) had two findings:

| Request | Size over the network | Time | Rows |
|---|--:|--:|--:|
| Full watch, **with** `Accept-Encoding: gzip` | 610 KB | **0.99 s** | 3,845 |
| Deltas only (`hEven`/`RefID` from the previous response) | 0.6 KB | 0.35 s | 1 |
| Old MarketWatchPlus version, full | 425 KB | 1.66 s | 3,845 |

1. **The cause of the 15 seconds was the missing compression, not the data volume.** The initial recording script didn't send the `Accept-Encoding` header and received 3.5 MB raw. The collector uses httpx, which requests gzip by default, so it has always been around that 1-second figure.
2. **Fetching deltas works** and only saves 0.6 seconds.

**Decision:** The watch is fetched **in full** every minute. Fetching deltas saves 60% of one second, but requires state kept in the collector, accumulates drift if a response is lost, requires a full snapshot on every restart, and would make `replay` unable to reconstruct each cycle independently. A full snapshot is **stateless and self-healing**. If response time ever reaches a dangerous range (monitored via `raw_snapshots.latency_ms`), this decision will be revisited.

!!! note "Lesson"
    The assumption "it's slow, so caching is needed" was wrong before the second measurement. This ADR was deliberately not rewritten; a review section was added to it instead, so the decision trail stays visible.

## Day 6 Review: Two Fixes After the Load Test {#day-6-review-two-fixes-after-the-load-test}

The [load test](../09-quality-engineering.md#load-test) exposed two weaknesses in layer ④:

1. **Cache stampede at the tick moment.** The cache key is tied to the tick, so with every tick all keys expire simultaneously and every open panel misses in the same second: 56 computations instead of 6 for 20 users. This was a direct cost of the "invalidate by tick" choice. **Fix:** computation of each key became *single-flight* per process, and concurrent requests wait on the same result.
2. **A hidden query before the cache.** The default `?date=` (latest session) was queried from ClickHouse on every request, even for 304 responses. **Fix:** the latest session per tick is now kept in memory.

Result: 304 response time went from 11.4 to 2.9 ms, and cached-mode throughput went from 132 to 283 requests per second (349 with ETag). **New consequence:** single-flight is process-level. With multiple workers, each worker computes it once. A distributed version with a Redis lock is covered in [Next Steps](../10-limitations.md#next-steps).

## Post-Day-7 Review: The Cache Version Isn't Just the Tick {#post-day-7-review-the-cache-version-isnt-just-the-tick}

The cache key and ETag were built on the latest tick id, assuming **data only changes with a fresh tick**. Two things broke that assumption:

1. **Fresh data under an old tick.** Backfilling missed minutes ([ADR 0012](0012-intraday-backfill.md)) writes rows after market close, when no fresh tick is coming. A fund page opened before that kept getting the same dataless 304 response until the next day. Now `TickBus.bump()` changes the id with a suffix (`…12:29:00+03:30#backfill.…`) and publishes on the same channel; caches are invalidated and open panels update.
2. **Responses that depend on the clock.** `is_live` and the holiday banner depend on the current time, not on the data. A response cached at 12:29 kept returning 304 even after close. Now the cache version is `{tick}|{open or closed}` (`api/cache.py: versioned`).
