-- 0002: columns and tables discovered while mapping real TSETMC payloads.

-- When the fund last computed its NAV. Lets validation tell a fresh NAV from a
-- stale one (NAVs are published every few minutes, not every tick).
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS nav_at Nullable(DateTime('Asia/Tehran')) AFTER nav_subscription;

-- Institutional rial flows and counts (0001 only had the individual side).
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS inst_buy_value UInt64 AFTER ind_sell_value;
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS inst_sell_value UInt64 AFTER inst_buy_value;
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS inst_buy_count UInt32 AFTER ind_sell_count;
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS inst_sell_count UInt32 AFTER inst_buy_count;

-- Turnover on the fund's secondary boards (block trades, ISIN …0002/…0004),
-- rolled up into the primary instrument.
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS block_volume UInt64 AFTER trade_count;
ALTER TABLE fund_ticks ADD COLUMN IF NOT EXISTS block_value UInt64 AFTER block_volume;

-- Reference data: exchange (TSE / IFB) and trading board.
ALTER TABLE funds ADD COLUMN IF NOT EXISTS market LowCardinality(String) AFTER fund_type;
ALTER TABLE funds ADD COLUMN IF NOT EXISTS board LowCardinality(String) AFTER market;

-- Market-wide context per tick: the benchmark every fund is compared against.
CREATE TABLE IF NOT EXISTS market_ticks
(
    ts               DateTime('Asia/Tehran'),
    run_id           UUID,
    index_value      Float64,
    index_change     Float64,
    eq_index_value   Float64,
    eq_index_change  Float64,
    market_value     Float64,
    state            LowCardinality(String),
    ingested_at      DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY ts;
