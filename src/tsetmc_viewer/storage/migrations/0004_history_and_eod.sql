-- 0004: official daily history (backfill + after-close refresh) and an
-- end-of-day rollup of the live minute data.

-- One row per fund per trading day, from TSETMC's daily endpoints. Unlike the
-- intraday estimate, individual/institutional values here are official.
CREATE TABLE IF NOT EXISTS fund_history_daily
(
    trade_date       Date,
    ins_code         String,
    open_price       UInt64,
    high_price       UInt64,
    low_price        UInt64,
    close_price      UInt64,
    last_price       UInt64,
    prev_close       UInt64,
    volume           UInt64,
    value            UInt64,
    trade_count      UInt32,
    ind_buy_volume   UInt64,
    ind_sell_volume  UInt64,
    inst_buy_volume  UInt64,
    inst_sell_volume UInt64,
    ind_buy_value    UInt64,
    ind_sell_value   UInt64,
    inst_buy_value   UInt64,
    inst_sell_value  UInt64,
    ind_buy_count    UInt32,
    ind_sell_count   UInt32,
    inst_buy_count   UInt32,
    inst_sell_count  UInt32,
    updated_at       DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYear(trade_date)
ORDER BY (ins_code, trade_date);

-- End-of-day state of the live data, maintained on insert by a materialized
-- view. Only "last value of the day" aggregates are used: they are idempotent,
-- so replays and forward-filled duplicates in fund_ticks cannot double-count
-- (a sum()-based rollup over a ReplacingMergeTree source would).
CREATE TABLE IF NOT EXISTS fund_eod
(
    trade_date     Date,
    ins_code       String,
    last_ts        SimpleAggregateFunction(max, DateTime('Asia/Tehran')),
    close_price    AggregateFunction(argMax, UInt64, Tuple(ts DateTime('Asia/Tehran'), ingested_at DateTime64(3, 'Asia/Tehran'))),
    value          AggregateFunction(argMax, UInt64, Tuple(ts DateTime('Asia/Tehran'), ingested_at DateTime64(3, 'Asia/Tehran'))),
    nav_redemption AggregateFunction(argMax, Nullable(UInt64), Tuple(ts DateTime('Asia/Tehran'), ingested_at DateTime64(3, 'Asia/Tehran'))),
    ind_net_value  AggregateFunction(argMax, Int64, Tuple(ts DateTime('Asia/Tehran'), ingested_at DateTime64(3, 'Asia/Tehran')))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ins_code, trade_date);

-- The ordering key is CAST to the column's named tuple explicitly: whether a
-- bare (ts, ingested_at) is named depends on enable_named_columns_in_function_tuple,
-- whose default differs between 24.8 patch releases (on in 24.8.4, off in 24.8.14).
CREATE MATERIALIZED VIEW IF NOT EXISTS fund_eod_mv TO fund_eod AS
WITH CAST((ts, ingested_at), 'Tuple(ts DateTime(\'Asia/Tehran\'), ingested_at DateTime64(3, \'Asia/Tehran\'))') AS version
SELECT
    toDate(ts) AS trade_date,
    ins_code,
    max(ts) AS last_ts,
    argMaxState(close_price, version) AS close_price,
    argMaxState(value, version) AS value,
    argMaxState(nav_redemption, version) AS nav_redemption,
    argMaxState(toInt64(ind_buy_value) - toInt64(ind_sell_value), version) AS ind_net_value
FROM fund_ticks
GROUP BY trade_date, ins_code;
