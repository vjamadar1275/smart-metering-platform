-- Reference DDL for gold.dma_analytics — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_daily_marts.py (see
-- bundles/gold_batch_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- IMPORTANT: estimated_supply_liters/non_revenue_water_* are derived from
-- reference.dim_dma.target_nrw_pct, NOT real bulk/production-meter
-- telemetry — this platform has no bulk supply-meter data source
-- integrated yet. See src/libs/common/gold_transforms.py:compute_dma_analytics
-- and ADR-0011 for the full explanation and open item. night_flow_anomaly_flag,
-- by contrast, is computed from real metered data only.

CREATE TABLE IF NOT EXISTS gold.dma_analytics (
    dma_id                             STRING      COMMENT 'District Meter Area identifier.',
    dma_name                             STRING,
    zone                                   STRING,
    reading_date                            DATE        COMMENT 'Calendar day (UTC) this row summarizes.',
    population_served                        INT,
    active_meter_count                        INT         COMMENT 'Distinct meters with at least one reading in this DMA on this day.',
    metered_consumption_liters                 DOUBLE      COMMENT 'Sum of gold.daily_usage.consumption_liters for meters in this DMA. Real, metered data.',
    target_nrw_pct                              DOUBLE      COMMENT 'From reference.dim_dma — the utility''s water-balance-audit target, not a measured value.',
    estimated_supply_liters                      DOUBLE      COMMENT 'PROXY: metered_consumption_liters / (1 - target_nrw_pct/100). Not real bulk-supply telemetry — see note above.',
    non_revenue_water_liters                      DOUBLE      COMMENT 'PROXY: estimated_supply_liters - metered_consumption_liters.',
    non_revenue_water_pct                          DOUBLE      COMMENT 'PROXY: non_revenue_water_liters / estimated_supply_liters * 100.',
    avg_night_flow_lpm                              DOUBLE      COMMENT 'Average flow rate across this DMA''s meters during 02:00-04:00 UTC. Real, metered data.',
    trailing_14d_avg_night_flow_lpm                  DOUBLE      COMMENT 'Average avg_night_flow_lpm over the 14 days before this one (excludes this day).',
    night_flow_anomaly_flag                            BOOLEAN     COMMENT 'True if avg_night_flow_lpm > 2x trailing_14d_avg_night_flow_lpm — a real leak indicator, independent of the supply-data proxy above.',
    meters_with_usage_anomaly                            INT         COMMENT 'Count of meters in this DMA flagged by gold.daily_usage.usage_anomaly_flag on this day.'
)
USING DELTA
CLUSTER BY (dma_id, reading_date)
COMMENT 'District Meter Area balance and leak indicators. See docs/architecture/ARCHITECTURE.md#4-silver--gold and ADR-0011 for the estimated_supply_liters proxy caveat.'
TBLPROPERTIES (
    'quality' = 'gold'
);
