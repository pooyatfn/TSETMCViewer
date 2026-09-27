-- 0003: data-quality counters per collection cycle.

-- Number of data_quality_log rows the cycle produced.
ALTER TABLE collection_runs ADD COLUMN IF NOT EXISTS issues UInt32 AFTER received_funds;

-- Ticks created by forward-filling (gaps and funds missing from the feed).
ALTER TABLE collection_runs ADD COLUMN IF NOT EXISTS filled UInt32 AFTER issues;

-- Ticks whose values the validator changed (band, OHLC, cumulative, NAV carry).
ALTER TABLE collection_runs ADD COLUMN IF NOT EXISTS repaired UInt32 AFTER filled;
