-- Reference DDL for gold.executive_dashboard — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_daily_marts.py (see
-- bundles/gold_batch_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- One row per most-recently-complete day (small, unclustered) — tuned for
-- a Phase 6 Power BI executive report. systemwide_nrw_pct inherits the
-- estimated_supply_liters proxy caveat from gold.dma_analytics — see that
-- table's DDL comment and ADR-0011.

CREATE TABLE IF NOT EXISTS gold.executive_dashboard (
    total_consumption_liters         DOUBLE      COMMENT 'Total metered consumption across all customers for the most recently complete day.',
    total_customers                    BIGINT,
    residential_liters                   DOUBLE,
    commercial_liters                      DOUBLE,
    industrial_liters                        DOUBLE,
    unknown_segment_liters                     DOUBLE      COMMENT 'Consumption from customers with account_type = UNKNOWN (no matching reference.dim_customer row) — a data-completeness signal in its own right.',
    high_usage_customer_count                    BIGINT      COMMENT 'Customers flagged by gold.customer_analytics.high_usage_flag.',
    total_non_revenue_water_liters                 DOUBLE      COMMENT 'PROXY — see gold.dma_analytics and ADR-0011.',
    total_estimated_supply_liters                    DOUBLE      COMMENT 'PROXY — see gold.dma_analytics and ADR-0011.',
    systemwide_nrw_pct                                 DOUBLE      COMMENT 'PROXY — total_non_revenue_water_liters / total_estimated_supply_liters * 100.',
    dma_leak_flag_count                                  INT         COMMENT 'DMAs flagged by gold.dma_analytics.night_flow_anomaly_flag — real, not a proxy.',
    as_of                                                  TIMESTAMP   COMMENT 'Wall-clock time this snapshot was computed.'
)
USING DELTA
COMMENT 'Top-line KPI mart for executive reporting, tuned for a Phase 6 Power BI executive report. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'gold'
);
