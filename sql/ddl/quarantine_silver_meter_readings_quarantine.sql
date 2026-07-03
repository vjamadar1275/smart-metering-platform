-- Reference DDL for quarantine.silver_meter_readings_quarantine —
-- documentation only.
--
-- The actual table is created and evolved declaratively by the Lakeflow
-- pipeline at src/pipelines/silver/silver_meter_readings.py. Do not run
-- this file against a live catalog — see sql/ddl/silver_meter_readings.sql
-- for the same convention.

CREATE TABLE IF NOT EXISTS quarantine.silver_meter_readings_quarantine (
    meter_id            STRING      COMMENT 'As received from Bronze; may be NULL if this is the violation.',
    reading_timestamp    TIMESTAMP   COMMENT 'As received from Bronze; may be NULL if this is the violation.',
    ingest_timestamp      TIMESTAMP,
    reading_value          DOUBLE,
    unit                    STRING,
    dma_id                   STRING,
    raw_payload               BINARY      COMMENT 'Original Avro bytes, carried through from Bronze so a bad record can be re-examined without re-reading Bronze.',
    quarantine_reasons        ARRAY<STRING> COMMENT 'One or more reason codes from src/libs/quality/expectations.py explaining every rule this record violated — never just the first.',
    kafka_partition             INT,
    kafka_offset                 BIGINT,
    ingest_date                   DATE        COMMENT 'Partition column, carried through from Bronze.',
    quarantined_at                 TIMESTAMP   COMMENT 'Wall-clock time this row was written to quarantine, for triage SLA tracking.'
)
USING DELTA
PARTITIONED BY (ingest_date)
COMMENT 'Silver validation failures, preserved with reason codes for triage — never silently dropped. See docs/architecture/ARCHITECTURE.md#3-bronze--silver and ADR-0010.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'quarantine'
);
