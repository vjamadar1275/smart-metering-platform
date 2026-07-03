-- Reference DDL for quarantine.silver_meter_readings — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/silver/silver_meter_readings.py, and appended
-- to by the nightly batch job
-- src/jobs/silver_late_arrival_reconciliation.py for late-arriving rows
-- that also fail validation. Do not run this file against a live catalog;
-- it exists so the table's shape is reviewable in plain SQL without reading
-- Python, per CONTRIBUTING.md's DDL documentation convention.
--
-- Same column shape as silver.meter_readings plus `reason_code` and
-- `quarantined_at` — quarantined rows carry every enriched field they were
-- validated with, so triage doesn't require re-joining back to Bronze.

CREATE TABLE IF NOT EXISTS quarantine.silver_meter_readings (
    meter_id              STRING      COMMENT 'Unique smart meter identifier. May not exist in reference.dim_meter — see is_known_meter.',
    reading_timestamp      TIMESTAMP   COMMENT 'Device-clock timestamp of the reading, UTC.',
    ingest_timestamp        TIMESTAMP   COMMENT 'Gateway-clock timestamp when forwarded to Event Hubs, UTC.',
    reading_value_liters    DOUBLE      COMMENT 'Standardized reading value, if `unit` was recognized (NULL otherwise — see reason_code).',
    flow_rate                DOUBLE      COMMENT 'Instantaneous flow rate, liters/minute. Nullable.',
    battery_pct              INT         COMMENT 'Remaining battery percentage, 0-100. Nullable.',
    signal_quality           INT         COMMENT 'RSSI or equivalent, 0-100. Nullable.',
    dma_id                   STRING      COMMENT 'District Meter Area this reading was reported under. May be NULL — see reason_code.',
    dma_name                  STRING      COMMENT 'Enriched from reference.dim_dma, "UNKNOWN" if unmatched.',
    dma_zone                  STRING      COMMENT 'Enriched from reference.dim_dma.',
    firmware_version          STRING,
    sequence_no                BIGINT,
    customer_id                STRING      COMMENT 'Enriched from reference.dim_meter, if the meter was known.',
    account_name               STRING,
    account_type                STRING      COMMENT 'RESIDENTIAL | COMMERCIAL | INDUSTRIAL | UNKNOWN.',
    service_address             STRING,
    meter_type                   STRING,
    meter_size_mm                INT,
    meter_status                  STRING      COMMENT 'ACTIVE | RETIRED | SUSPENDED | UNKNOWN.',
    is_known_meter                 BOOLEAN     COMMENT 'False if this reason_code is unknown_meter.',
    reading_date                    DATE,
    reason_code                      STRING      COMMENT 'The first Silver validation rule this row failed — see src/libs/quality/expectations.py:METER_READING_EXPECTATIONS for the full rule set and reason codes.',
    quarantined_at                    TIMESTAMP   COMMENT 'Wall-clock time this row was written to quarantine, for triage/aging reports.'
)
USING DELTA
COMMENT 'Meter readings that failed at least one Silver validation rule, retained with a reason code rather than dropped. See docs/architecture/ARCHITECTURE.md#3-bronze--silver.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'quarantine'
);
