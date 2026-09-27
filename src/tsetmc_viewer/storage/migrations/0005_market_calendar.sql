-- 0005: what the market actually did on days the calendar got wrong.
-- Written by the collector's session guard (domain/calendar.py, layer 3):
--   trading = 0 → a listed trading day on which TSETMC never showed a trade
--   trading = 1 → a listed holiday on which the market did trade
-- Loaded back on start, so a restart does not repeat the discovery.
CREATE TABLE IF NOT EXISTS market_calendar
(
    day         Date,
    trading     UInt8,
    note        String,
    recorded_at DateTime64(3, 'Asia/Tehran')
)
ENGINE = ReplacingMergeTree(recorded_at)
ORDER BY day;
