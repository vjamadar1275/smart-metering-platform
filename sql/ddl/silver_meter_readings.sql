-- Reference DDL for silver.meter_readings — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/silver/silver_meter_readings.py (see
-- bundles/silver_pipeline.yml for deployment). Do not run this file
-- against a live catalog; it exists so the table's shape is reviewable in
-- plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.

CREATE TABLE IF NOT EXISTS silver.meter_readings (
    meter_id                 STRING      COMMENT 'Unique smart meter identifier. Part of the MERGE key.',
    reading_timestamp         TIMESTAMP   COMMENT 'Device-clock timestamp of the reading, UTC. Part of the MERGE key.',
    ingest_timestamp           TIMESTAMP   COMMENT 'Gateway-clock timestamp when forwarded to Event Hubs, UTC.',
    reading_value               DOUBLE      COMMENT 'Cumulative volumetric reading, in the original `unit`.',
    unit                         STRING      COMMENT 'LITERS | GALLONS | CUBIC_METERS, as reported by the meter.',
    reading_value_liters          DOUBLE      COMMENT 'reading_value standardized to liters — the column Gold aggregates on.',
    reading_local_timestamp        TIMESTAMP   COMMENT 'reading_timestamp shifted by the serving DMA''s utc_offset_minutes, for local-time reporting.',
    flow_rate                       DOUBLE      COMMENT 'Instantaneous flow rate, liters/minute. Nullable.',
    battery_pct                     INT         COMMENT 'Remaining battery percentage, 0-100. Nullable; out-of-range values are tracked as a soft expectation, not quarantined.',
    signal_quality                   INT         COMMENT 'RSSI or equivalent, 0-100. Nullable; same soft-expectation treatment as battery_pct.',
    dma_id                            STRING      COMMENT 'District Meter Area this meter belongs to, as reported by telemetry.',
    ref_customer_id                    STRING      COMMENT 'Enriched from reference.dim_meter: the billing account this meter belongs to.',
    ref_meter_dma_id                    STRING      COMMENT 'Enriched from reference.dim_meter: the DMA the meter master record assigns (should match dma_id; a mismatch would have been caught upstream by other means were this checked).',
    ref_meter_type                       STRING      COMMENT 'Enriched from reference.dim_meter: ULTRASONIC | MECHANICAL | AMR.',
    ref_meter_size_mm                     INT         COMMENT 'Enriched from reference.dim_meter: nominal meter bore size, millimeters.',
    ref_dma_name                           STRING      COMMENT 'Enriched from reference.dim_dma: human-readable DMA name.',
    ref_dma_region                          STRING      COMMENT 'Enriched from reference.dim_dma: operating region/division.',
    firmware_version                         STRING,
    sequence_no                               BIGINT      COMMENT 'Per-meter monotonic sequence number, carried through from Bronze.',
    kafka_partition                            INT         COMMENT 'Carried through from Bronze, for lineage/debugging.',
    kafka_offset                                BIGINT      COMMENT 'Carried through from Bronze; used as the apply_changes tie-breaker for same-timestamp redeliveries.',
    ingest_date                                  DATE        COMMENT 'Partition column: DATE(ingest_timestamp), carried through from Bronze.'
)
USING DELTA
PARTITIONED BY (ingest_date)
COMMENT 'Validated, deduplicated, unit-standardized, enriched meter readings — the single source of truth Gold builds on. MERGE-based dedup (Lakeflow apply_changes) keyed on (meter_id, reading_timestamp). See docs/architecture/ARCHITECTURE.md#3-bronze--silver and ADR-0010.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'silver'
);
