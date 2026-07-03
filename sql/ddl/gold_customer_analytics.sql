-- Reference DDL for gold.customer_analytics — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/gold/gold_daily_marts.py (see
-- bundles/gold_batch_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.

CREATE TABLE IF NOT EXISTS gold.customer_analytics (
    customer_id                STRING      COMMENT 'Unique customer/billing-account identifier.',
    reading_date                 DATE        COMMENT 'Calendar day (UTC) this row summarizes.',
    consumption_liters             DOUBLE      COMMENT 'Sum of gold.daily_usage.consumption_liters across all meters this customer holds.',
    meter_count                     INT         COMMENT 'Distinct meters this customer holds with a reading on this day.',
    account_type                     STRING,
    rolling_30d_avg_liters             DOUBLE      COMMENT 'Average consumption_liters over the trailing 30 days (including this day).',
    recent_7d_avg_liters                 DOUBLE      COMMENT 'Average consumption_liters over the trailing 7 days (including this day).',
    prior_7d_avg_liters                   DOUBLE      COMMENT 'Average consumption_liters over the 7 days before that. NULL for a customer''s first 2 weeks.',
    trend_direction                        STRING      COMMENT 'INCREASING | DECREASING | STABLE | INSUFFICIENT_HISTORY, comparing recent_7d_avg_liters to prior_7d_avg_liters.',
    high_usage_flag                          BOOLEAN     COMMENT 'True if consumption_liters > 2x rolling_30d_avg_liters.'
)
USING DELTA
CLUSTER BY (customer_id, reading_date)
COMMENT 'Customer-level usage trends and billing-relevant aggregates, rolled up from gold.daily_usage. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'gold'
);
