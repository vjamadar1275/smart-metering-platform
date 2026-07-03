"""Silver layer: validated, deduplicated, enriched meter readings.

Lakeflow Declarative Pipeline (see bundles/silver_pipeline.yml for
deployment, docs/architecture/ARCHITECTURE.md#3-bronze--silver for the
design, ADR-0010 for the quarantine/late-arrival split rationale).

Flow, in order:
  1. `stg_enriched_readings` (temporary view): reads bronze.meter_telemetry,
     left-joins current reference dimension rows, standardizes units to
     liters and adds a local-time offset, and computes per-row
     `quarantine_reasons` (see src/libs/quality/expectations.py). Nothing
     is dropped here — every Bronze row that reaches this view is either
     routed to silver.meter_readings or quarantine.silver_meter_readings_
     quarantine below, with a reason code either way.
  2. `quarantine.silver_meter_readings_quarantine`: the invalid rows,
     preserved with their reason codes for triage (not dropped).
  3. `valid_readings` (temporary view): the valid rows only.
  4. `silver.meter_readings`: a MERGE-based dedup (Lakeflow `apply_changes`,
     Databricks' declarative equivalent of a keyed MERGE) keyed on
     (meter_id, reading_timestamp), so retried/redelivered events collapse
     to one row. A 24-hour watermark on reading_timestamp bounds the
     streaming state this requires; a reading arriving later than that is
     dropped from *this* continuous flow by Structured Streaming's own
     watermark semantics, not by us — see ADR-0010 for why late-arrival
     reconciliation is therefore a separate batch job
     (src/jobs/silver_late_arrival_reconciliation.py) rather than a second
     flow into this same pipeline.

Deliberately NOT implemented here: a "plausible delta from the meter's
previous reading" expectation. Evaluating it would require this pipeline
to read silver.meter_readings (its own apply_changes target) as an
upstream input — an illegal self-referential dependency in Lakeflow's
dependency graph. That check is inherently statistical (what delta is
"plausible" varies by meter/season/usage pattern) rather than a fixed
business rule, so it is deferred to Phase 7's anomaly-detection model
(ADR-0008) instead of forced into a hard-coded Silver expectation.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from src.libs.common.units import to_liters
from src.libs.quality.expectations import SOFT_EXPECTATIONS, with_quarantine_reasons

_conf = spark.conf
WATERMARK_HOURS = int(_conf.get("smartmeter.silver.watermark_hours", "24"))
MAX_CLOCK_SKEW_HOURS = int(_conf.get("smartmeter.silver.max_clock_skew_hours", "1"))
MAX_PLAUSIBLE_LITERS = float(_conf.get("smartmeter.silver.max_plausible_liters", "1000000000"))


def _current_dim(table_name: str):
    """Batch snapshot of a SCD2 reference dimension's current rows.

    A genuinely streaming join against a dimension table would need its
    own watermark/state management for a table that changes rarely and
    intentionally lags (SCD2 changes are deliberate, out-of-band edits,
    not something Silver needs to react to within the same micro-batch) —
    re-read as a fresh batch snapshot each triggered update instead, which
    is Lakeflow's standard pattern for slowly-changing dimension joins.
    """
    return spark.read.table(table_name).filter("is_current")


@dp.temporary_view(name="stg_enriched_readings")
@dp.expect_all(SOFT_EXPECTATIONS)
def stg_enriched_readings():
    bronze = spark.readStream.table("bronze.meter_telemetry").withWatermark(
        "reading_timestamp", f"{WATERMARK_HOURS} hours"
    )

    dim_meter = _current_dim("reference.dim_meter").select(
        F.col("meter_id"),
        F.col("customer_id").alias("ref_customer_id"),
        F.col("dma_id").alias("ref_meter_dma_id"),
        F.col("meter_type").alias("ref_meter_type"),
        F.col("meter_size_mm").alias("ref_meter_size_mm"),
        F.col("expected_unit").alias("ref_meter_expected_unit"),
        F.col("install_date").alias("ref_meter_install_date"),
        F.col("status").alias("ref_meter_status"),
    )
    dim_dma = _current_dim("reference.dim_dma").select(
        F.col("dma_id").alias("ref_dma_id"),
        F.col("dma_name").alias("ref_dma_name"),
        F.col("region").alias("ref_dma_region"),
        F.col("utc_offset_minutes").alias("ref_dma_utc_offset_minutes"),
    )

    enriched = (
        bronze.join(F.broadcast(dim_meter), on="meter_id", how="left")
        .join(
            F.broadcast(dim_dma),
            on=bronze["dma_id"] == F.col("ref_dma_id"),
            how="left",
        )
        .withColumn("reading_value_liters", to_liters(F.col("reading_value"), F.col("unit")))
        .withColumn(
            "reading_local_timestamp",
            F.col("reading_timestamp")
            + F.make_interval(mins=F.coalesce(F.col("ref_dma_utc_offset_minutes"), F.lit(0))),
        )
    )

    return with_quarantine_reasons(
        enriched,
        max_plausible_liters=MAX_PLAUSIBLE_LITERS,
        max_clock_skew_hours=MAX_CLOCK_SKEW_HOURS,
    )


@dp.table(
    name="quarantine.silver_meter_readings_quarantine",
    comment=(
        "Bronze meter telemetry that failed one or more Silver validation "
        "rules, preserved with reason codes for triage — never silently "
        "dropped. See src/libs/quality/expectations.py for the rule set."
    ),
    table_properties={
        "delta.enableChangeDataFeed": "true",
        "quality": "quarantine",
    },
    partition_cols=["ingest_date"],
)
def silver_meter_readings_quarantine():
    return (
        spark.readStream.table("stg_enriched_readings")
        .filter(~F.col("is_valid"))
        .select(
            "meter_id",
            "reading_timestamp",
            "ingest_timestamp",
            "reading_value",
            "unit",
            "dma_id",
            "raw_payload",
            "quarantine_reasons",
            "kafka_partition",
            "kafka_offset",
            "ingest_date",
        )
        .withColumn("quarantined_at", F.current_timestamp())
    )


@dp.temporary_view(name="valid_readings")
def valid_readings():
    # Projects down to exactly silver.meter_readings' documented column set
    # (sql/ddl/silver_meter_readings.sql) — drops the raw_payload/parse_error
    # (quarantine-only, diagnostic) and the ref_meter_status/expected_unit/
    # install_date columns (validation inputs only, not business attributes
    # worth carrying into the single source of truth).
    return (
        spark.readStream.table("stg_enriched_readings")
        .filter("is_valid")
        .select(
            "meter_id",
            "reading_timestamp",
            "ingest_timestamp",
            "reading_value",
            "unit",
            "reading_value_liters",
            "reading_local_timestamp",
            "flow_rate",
            "battery_pct",
            "signal_quality",
            "dma_id",
            F.col("ref_customer_id"),
            F.col("ref_meter_dma_id"),
            F.col("ref_meter_type"),
            F.col("ref_meter_size_mm"),
            F.col("ref_dma_name"),
            F.col("ref_dma_region"),
            "firmware_version",
            "sequence_no",
            "kafka_partition",
            "kafka_offset",
            "ingest_date",
        )
    )


dp.create_streaming_table(
    name="silver.meter_readings",
    comment=(
        "Validated, deduplicated, unit-standardized (liters), enriched "
        "meter readings — the single source of truth Gold builds on. "
        "MERGE-based dedup keyed on (meter_id, reading_timestamp) via "
        "Lakeflow apply_changes; see ADR-0010 for the late-arrival "
        "reconciliation design this table depends on for completeness "
        "beyond the streaming watermark."
    ),
    table_properties={
        "delta.enableChangeDataFeed": "true",
        "quality": "silver",
    },
    partition_cols=["ingest_date"],
)

dp.apply_changes(
    target="silver.meter_readings",
    source="valid_readings",
    keys=["meter_id", "reading_timestamp"],
    # Tie-break duplicate keys (redelivered/retried events) by picking the
    # attempt with the latest gateway ingest_timestamp, then the highest
    # Kafka offset if two attempts share an ingest_timestamp exactly.
    sequence_by=F.struct(F.col("ingest_timestamp"), F.col("kafka_offset")),
    stored_as_scd_type=1,
)
