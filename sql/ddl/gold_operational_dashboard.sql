-- Reference DDL for gold.operational_dashboard — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_daily_marts.py (see
-- bundles/gold_batch_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- One row per pipeline run (small, unclustered) — a live-ish operational
-- snapshot, not a historical table. Query gold.daily_usage/gold.dma_analytics
-- for trend history.

CREATE TABLE IF NOT EXISTS gold.operational_dashboard (
    active_meter_count            INT         COMMENT 'Distinct meters with a reading today.',
    readings_ingested               BIGINT      COMMENT 'Total Silver readings today.',
    low_battery_reading_count         INT         COMMENT 'Readings today reporting battery_pct below the low-battery threshold — see src/libs/common/gold_transforms.py:LOW_BATTERY_THRESHOLD_PCT.',
    quarantined_count                   BIGINT      COMMENT 'Readings quarantined today (see quarantine.silver_meter_readings).',
    quarantine_rate_pct                   DOUBLE      COMMENT 'quarantined_count / (readings_ingested + quarantined_count) * 100 — a data-quality health signal.',
    dma_leak_flag_count                     INT         COMMENT 'DMAs currently flagged by gold.dma_analytics.night_flow_anomaly_flag.',
    as_of                                     TIMESTAMP   COMMENT 'Wall-clock time this snapshot was computed.'
)
USING DELTA
COMMENT 'Fleet-health snapshot for the operations team, tuned for a Phase 6 Power BI operational report. One row per pipeline run. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'gold'
);
