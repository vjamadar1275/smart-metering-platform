-- Reference DDL for reference.dim_customer — documentation only.
--
-- The actual table is created and populated by src/jobs/seed_reference_data.py
-- (see bundles/seed_reference_data_job.yml for deployment). Do not run this
-- file against a live catalog; it exists so the table's shape is reviewable
-- in plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- SCD Type 2, same rationale as reference.dim_meter: billing account type or
-- address can change over a customer's tenure, and past Gold aggregates
-- must join to the account details that were actually in effect then.

CREATE TABLE IF NOT EXISTS reference.dim_customer (
    customer_id           STRING      COMMENT 'Unique customer/billing-account identifier. Joins from reference.dim_meter.customer_id.',
    account_name           STRING      COMMENT 'Billing account holder name (individual or business).',
    account_type            STRING      COMMENT 'RESIDENTIAL | COMMERCIAL | INDUSTRIAL — matches the meter_type of the meters this account holds.',
    service_address         STRING      COMMENT 'Primary service address.',
    connection_date          DATE        COMMENT 'Date this customer account was connected to service.',
    billing_cycle_day        INT         COMMENT 'Day of month (1-28) this account''s billing cycle closes on.',
    effective_start_date   DATE        COMMENT 'SCD2: date this version of the customer record became effective.',
    effective_end_date     DATE        COMMENT 'SCD2: date this version was superseded. NULL for the current version.',
    is_current              BOOLEAN     COMMENT 'SCD2: true for exactly one row per customer_id — the version Silver enrichment joins against.'
)
USING DELTA
COMMENT 'Customer/billing-account dimension (SCD Type 2). Reference data joined into Silver during meter/customer/DMA enrichment. See docs/architecture/ARCHITECTURE.md#3-bronze--silver.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'reference'
);
