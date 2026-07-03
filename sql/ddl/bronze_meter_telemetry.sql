-- Reference DDL for bronze.meter_telemetry — documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/bronze/bronze_meter_telemetry.py (see
-- bundles/bronze_pipeline.yml for deployment). Do not run this file against
-- a live catalog; it exists so the table's shape is reviewable in plain SQL
-- without reading Python, per CONTRIBUTING.md's DDL documentation convention.

CREATE TABLE IF NOT EXISTS bronze.meter_telemetry (
    meter_id          STRING      COMMENT 'Unique smart meter identifier.',
    reading_timestamp  TIMESTAMP   COMMENT 'Device-clock timestamp of the reading, UTC.',
    ingest_timestamp   TIMESTAMP   COMMENT 'Gateway-clock timestamp when forwarded to Event Hubs, UTC.',
    reading_value      DOUBLE      COMMENT 'Cumulative volumetric reading, in `unit`.',
    unit                STRING      COMMENT 'LITERS | GALLONS | CUBIC_METERS.',
    flow_rate           DOUBLE      COMMENT 'Instantaneous flow rate, liters/minute. Nullable: not all firmware reports it.',
    battery_pct         INT         COMMENT 'Remaining battery percentage, 0-100. Nullable.',
    signal_quality      INT         COMMENT 'RSSI or equivalent, 0-100. Nullable.',
    dma_id              STRING      COMMENT 'District Meter Area this meter belongs to.',
    firmware_version    STRING,
    sequence_no          BIGINT      COMMENT 'Monotonically increasing per-meter sequence number; used by Silver for gap/duplicate detection.',
    raw_payload          BINARY      COMMENT 'Original Avro bytes as received, preserved so a parsing bug is recoverable by reprocessing Bronze rather than re-ingesting from the field.',
    parse_error          STRING      COMMENT 'Avro deserialization error message, if any (parsed fields above are NULL when this is set).',
    kafka_partition      INT         COMMENT 'Event Hubs partition the record was read from (Kafka-protocol view).',
    kafka_offset         BIGINT      COMMENT 'Offset within kafka_partition.',
    kafka_timestamp      TIMESTAMP   COMMENT 'Event Hubs enqueue time (Kafka-protocol view).',
    ingest_date          DATE        COMMENT 'Partition column: DATE(ingest_timestamp).',
    ingested_at           TIMESTAMP   COMMENT 'Wall-clock time this row was written to Bronze, for pipeline lineage/debugging.'
)
USING DELTA
PARTITIONED BY (ingest_date)
COMMENT 'Raw, immutable smart meter telemetry as received from Event Hubs. Append-only, schema-evolved, exactly-once via Structured Streaming checkpointing. See docs/architecture/ARCHITECTURE.md#2-ingestion--bronze-structured-streaming.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true',
    'quality' = 'bronze'
);
