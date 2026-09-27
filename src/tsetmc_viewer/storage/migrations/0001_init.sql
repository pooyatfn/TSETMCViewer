-- 0001: core tables.
-- ClickHouse has no transactional DDL, so every statement is idempotent
-- (IF NOT EXISTS) and a half-applied migration can simply be re-run.

-- Raw provider responses, stored before any parsing. Lets us replay ingestion
-- after a parser fix and audit exactly what the provider sent.
CREATE TABLE IF NOT EXISTS raw_snapshots
(
    fetched_at  DateTime64(3, 'Asia/Tehran'),
    run_id      UUID,
    source      LowCardinality(String),
    endpoint    LowCardinality(String),
    ins_code    String DEFAULT '',
    status_code UInt16,
    latency_ms  UInt32,
    attempts    UInt8,
    payload     String CODEC(ZSTD(6))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(fetched_at)
ORDER BY (source, endpoint, fetched_at)
TTL toDateTime(fetched_at) + INTERVAL 30 DAY DELETE;

-- One row per collector cycle: the heartbeat of the pipeline.
CREATE TABLE IF NOT EXISTS collection_runs
(
    run_id         UUID,
    started_at     DateTime64(3, 'Asia/Tehran'),
    finished_at    DateTime64(3, 'Asia/Tehran'),
    tick           DateTime('Asia/Tehran'),
    status         Enum8('ok' = 1, 'partial' = 2, 'failed' = 3),
    requests       UInt32,
    failed         UInt32,
    expected_funds UInt16,
    received_funds UInt16,
    note           String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY started_at;

-- Fund reference data (slowly changing). ReplacingMergeTree keeps the latest
-- version per ins_code; read with FINAL or argMax.
CREATE TABLE IF NOT EXISTS funds
(
    ins_code        String,
    symbol          String,
    name            String,
    isin            String,
    fund_type       LowCardinality(String),  -- equity | index | sector | leveraged | ...
    manager         String,
    custodian       String,
    fipiran_reg_no  Nullable(UInt32),
    inception_date  Nullable(Date),
    is_active       UInt8,
    source          LowCardinality(String),
    updated_at      DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY ins_code;

-- Daily fund-level facts that are not intraday (AUM, units, asset allocation).
CREATE TABLE IF NOT EXISTS fund_daily
(
    trade_date      Date,
    ins_code        String,
    units           Nullable(UInt64),
    net_assets      Nullable(Float64),
    stock_weight    Nullable(Float32),
    bond_weight     Nullable(Float32),
    cash_weight     Nullable(Float32),
    other_weight    Nullable(Float32),
    updated_at      DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ins_code, trade_date);

-- Cleaned 1-minute snapshots. Prices are integer Rials. Re-inserting the same
-- (ins_code, ts) is safe: the latest ingested_at wins.
CREATE TABLE IF NOT EXISTS fund_ticks
(
    ts                DateTime('Asia/Tehran'),
    ins_code          String,
    run_id            UUID,

    last_price        UInt64,
    close_price       UInt64,
    open_price        UInt64,
    high_price        UInt64,
    low_price         UInt64,
    prev_close        UInt64,
    volume            UInt64,
    value             UInt64,
    trade_count       UInt32,

    nav_redemption    Nullable(UInt64),
    nav_subscription  Nullable(UInt64),

    bid_price         UInt64,
    bid_volume        UInt64,
    ask_price         UInt64,
    ask_volume        UInt64,

    ind_buy_volume    UInt64,
    ind_sell_volume   UInt64,
    inst_buy_volume   UInt64,
    inst_sell_volume  UInt64,
    ind_buy_value     UInt64,
    ind_sell_value    UInt64,
    ind_buy_count     UInt32,
    ind_sell_count    UInt32,

    quality_flags     UInt32,
    ingested_at       DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (ins_code, ts);

-- Every validation finding and the corrective action taken.
CREATE TABLE IF NOT EXISTS data_quality_log
(
    ts        DateTime('Asia/Tehran'),
    run_id    UUID,
    ins_code  String,
    check     LowCardinality(String),
    severity  Enum8('info' = 1, 'warn' = 2, 'error' = 3),
    action    LowCardinality(String),
    detail    String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (ts, check)
TTL ts + INTERVAL 180 DAY DELETE;
