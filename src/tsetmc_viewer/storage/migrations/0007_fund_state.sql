-- 0007: trading status of each fund (مجاز، متوقف، محفوظ، ممنوع …) from
-- GetClosingPriceInfo.instrumentState, polled round robin: every fund on the first
-- cycle of the day, then each fund at least every five minutes (domain/status.py).
CREATE TABLE IF NOT EXISTS fund_state
(
    ts                DateTime('Asia/Tehran'),
    ins_code          String,
    code              LowCardinality(String),
    title             String,
    under_supervision UInt8,
    ingested_at       DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (ins_code, ts);
