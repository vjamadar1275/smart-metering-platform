-- Reference DDL for gold.hourly_consumption — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_hourly_consumption.py (see
-- bundles/gold_streaming_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.

CREATE TABLE IF NOT EXISTS gold.hourly_consumption (
    meter_id              STRING      COMMENT 'Unique smart meter identifier.',
    hour_start              TIMESTAMP   COMMENT 'Start of the 1-hour window (inclusive), UTC.',
    hour_end                TIMESTAMP   COMMENT 'End of the 1-hour window (exclusive), UTC.',
    consumption_liters       DOUBLE      COMMENT 'max(reading_value_liters) - min(reading_value_liters) within the window.',
    reading_count             INT         COMMENT 'Number of Silver readings that fell in this window.',
    avg_flow_rate_lpm          DOUBLE      COMMENT 'Average instantaneous flow rate, liters/minute, within the window.',
    min_battery_pct             INT         COMMENT 'Minimum reported battery percentage within the window.',
    avg_signal_quality           DOUBLE      COMMENT 'Average reported signal quality within the window.',
    dma_id                        STRING      COMMENT 'Carried through from silver.meter_readings.',
    dma_name                       STRING,
    customer_id                     STRING,
    meter_type                       STRING,
    account_type                      STRING
)
USING DELTA
CLUSTER BY (meter_id, hour_start)
COMMENT 'Per-meter, per-hour volumetric usage — the finest-grain Gold KPI, streamed continuously from silver.meter_readings. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'gold'
);
