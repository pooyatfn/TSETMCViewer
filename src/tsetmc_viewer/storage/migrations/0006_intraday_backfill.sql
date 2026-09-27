-- 0006: minutes rebuilt from today's trades when the collector started late (ADR 0012).
-- Kept apart from fund_ticks on purpose: these rows have price, volume, value and
-- trade count only (no individual/institutional flows, NAV or order book), so
-- nothing that reads flows or NAV can mistake them for a live snapshot.
CREATE TABLE IF NOT EXISTS fund_ticks_backfill
(
    ts          DateTime('Asia/Tehran'),
    ins_code    String,
    last_price  UInt64,
    volume      UInt64,
    value       UInt64,
    trade_count UInt32,
    ingested_at DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (ins_code, ts);

-- One decision per fund and day: stored, rejected (did not match the live ticks),
-- no_trades or error. Makes the backfill auditable and idempotent.
CREATE TABLE IF NOT EXISTS intraday_backfill_log
(
    day         Date,
    ins_code    String,
    status      LowCardinality(String),
    overlap     UInt16,
    matched     UInt16,
    minutes     UInt16,
    note        String,
    recorded_at DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(recorded_at)
ORDER BY (day, ins_code);
