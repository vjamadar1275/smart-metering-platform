-- Reference DDL for reference.dim_meter — documentation only.
--
-- The actual table is created and populated by src/jobs/seed_reference_data.py
-- (see bundles/seed_reference_data_job.yml for deployment). Do not run this
-- file against a live catalog; it exists so the table's shape is reviewable
-- in plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- Slowly Changing Dimension Type 2: a meter's DMA assignment, firmware, or
-- status can change over its lifetime (e.g. reassigned to a new District
-- Meter Area after network re-zoning). Silver (Phase 4) joins against only
-- the `is_current = true` row per meter_id; historical rows are retained so
-- Gold aggregates computed for a past period still join to the DMA/firmware
-- that was actually in effect at that time.

CREATE TABLE IF NOT EXISTS reference.dim_meter (
    meter_id            STRING      COMMENT 'Unique smart meter identifier. Matches bronze/silver meter_telemetry.meter_id.',
    dma_id               STRING      COMMENT 'District Meter Area this meter belongs to during this SCD2 version.',
    customer_id          STRING      COMMENT 'Customer this meter is billed to during this SCD2 version. Joins to reference.dim_customer.',
    meter_type            STRING      COMMENT 'RESIDENTIAL | COMMERCIAL | INDUSTRIAL.',
    meter_size_mm        INT         COMMENT 'Nominal meter bore size, millimeters (e.g. 15, 20, 25, 40).',
    install_date          DATE        COMMENT 'Date this physical meter was installed in the field.',
    latitude               DOUBLE      COMMENT 'Installation location latitude.',
    longitude              DOUBLE      COMMENT 'Installation location longitude.',
    status                 STRING      COMMENT 'ACTIVE | RETIRED | SUSPENDED.',
    effective_start_date  DATE        COMMENT 'SCD2: date this version of the meter record became effective.',
    effective_end_date    DATE        COMMENT 'SCD2: date this version was superseded. NULL for the current version.',
    is_current             BOOLEAN     COMMENT 'SCD2: true for exactly one row per meter_id — the version Silver enrichment joins against.'
)
USING DELTA
COMMENT 'Meter master dimension (SCD Type 2). Reference data joined into Silver during meter/customer/DMA enrichment. See docs/architecture/ARCHITECTURE.md#3-bronze--silver.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'reference'
);
