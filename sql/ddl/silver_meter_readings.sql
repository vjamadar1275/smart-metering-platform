-- Reference DDL for silver.meter_readings — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/silver/silver_meter_readings.py (a
-- dp.create_streaming_table + dp.create_auto_cdc_flow MERGE target — see
-- bundles/silver_pipeline.yml for deployment). Do not run this file against
-- a live catalog; it exists so the table's shape is reviewable in plain SQL
-- without reading Python, per CONTRIBUTING.md's DDL documentation
-- convention.

CREATE TABLE IF NOT EXISTS silver.meter_readings (
    meter_id              STRING      COMMENT 'Unique smart meter identifier.',
    reading_timestamp      TIMESTAMP   COMMENT 'Device-clock timestamp of the reading, UTC. Part of the MERGE dedup key with meter_id.',
    ingest_timestamp        TIMESTAMP   COMMENT 'Gateway-clock timestamp when forwarded to Event Hubs, UTC. AUTO CDC sequence_by column.',
    reading_value_liters    DOUBLE      COMMENT 'Cumulative volumetric reading, standardized to liters regardless of the meter''s reported unit.',
    flow_rate                DOUBLE      COMMENT 'Instantaneous flow rate, liters/minute. Nullable.',
    battery_pct              INT         COMMENT 'Remaining battery percentage, 0-100. Nullable.',
    signal_quality           INT         COMMENT 'RSSI or equivalent, 0-100. Nullable.',
    dma_id                   STRING      COMMENT 'District Meter Area this reading was reported under.',
    dma_name                  STRING      COMMENT 'Enriched from reference.dim_dma. "UNKNOWN" if dma_id has no matching dimension row.',
    dma_zone                  STRING      COMMENT 'Enriched from reference.dim_dma.',
    firmware_version          STRING,
    sequence_no                BIGINT      COMMENT 'Monotonically increasing per-meter sequence number, from the original telemetry event.',
    customer_id                STRING      COMMENT 'Enriched from reference.dim_meter (current SCD2 version at pipeline-run time).',
    account_name               STRING      COMMENT 'Enriched from reference.dim_customer.',
    account_type                STRING      COMMENT 'RESIDENTIAL | COMMERCIAL | INDUSTRIAL | UNKNOWN.',
    service_address             STRING      COMMENT 'Enriched from reference.dim_customer.',
    meter_type                   STRING      COMMENT 'Enriched from reference.dim_meter.',
    meter_size_mm                INT         COMMENT 'Enriched from reference.dim_meter.',
    meter_status                  STRING      COMMENT 'ACTIVE | RETIRED | SUSPENDED | UNKNOWN, from reference.dim_meter.',
    is_known_meter                 BOOLEAN     COMMENT 'True if this meter_id matched a reference.dim_meter row at enrichment time. Rows where this would be false are quarantined instead — see quarantine.silver_meter_readings.',
    reading_date                    DATE        COMMENT 'DATE(reading_timestamp). Liquid Clustering key alongside meter_id — see ADR-0004.'
)
USING DELTA
CLUSTER BY (meter_id, reading_date)
COMMENT 'Validated, deduplicated, enriched meter readings — the single source of truth Gold (Phase 5) builds on. See docs/architecture/ARCHITECTURE.md#3-bronze--silver.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'silver'
);
