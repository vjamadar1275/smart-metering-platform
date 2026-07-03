-- Reference DDL for gold.daily_usage — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_daily_marts.py (see
-- bundles/gold_batch_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.

CREATE TABLE IF NOT EXISTS gold.daily_usage (
    meter_id                    STRING      COMMENT 'Unique smart meter identifier.',
    reading_date                  DATE        COMMENT 'Calendar day (UTC) this row summarizes.',
    consumption_liters             DOUBLE      COMMENT 'max(reading_value_liters) - min(reading_value_liters) within the day.',
    reading_count                    INT         COMMENT 'Number of Silver readings on this day.',
    min_battery_pct                    INT,
    dma_id                               STRING,
    dma_name                              STRING,
    customer_id                            STRING,
    account_type                            STRING,
    meter_type                               STRING,
    trailing_7d_avg_liters                    DOUBLE      COMMENT 'Average consumption_liters over the 7 days before this one (excludes this day). NULL for a meter''s first 7 days.',
    usage_anomaly_flag                          BOOLEAN     COMMENT 'True if consumption_liters > 3x trailing_7d_avg_liters. A coarse signal, not a substitute for Phase 7''s Mosaic AI leak-detection model.'
)
USING DELTA
CLUSTER BY (meter_id, reading_date)
COMMENT 'Per-meter, per-day usage with a trailing-7-day baseline and usage-anomaly flag. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'gold'
);
