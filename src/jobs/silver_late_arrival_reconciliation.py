"""Nightly batch reconciliation for meter readings that arrive later than
Silver's streaming watermark tolerates.

Why this exists (see ADR-0010 for the full trade-off analysis): Silver's
continuous Lakeflow flow (src/pipelines/silver/silver_meter_readings.py)
deduplicates via a watermarked `apply_changes`, and Structured Streaming's
watermark semantics mean a reading arriving more than
`smartmeter.silver.watermark_hours` (default 24h) after the latest
event-time already seen is dropped by that flow — not persisted anywhere.
Rather than widen the watermark (which grows streaming state unboundedly
for a genuinely rare case — a meter reconnecting after a multi-day
outage), this plain batch Spark job runs nightly as a Databricks Job task
(NOT a Lakeflow pipeline; see ADR-0003's "isolate genuinely imperative
logic outside Lakeflow" guidance) and idempotently MERGEs any Bronze
readings from the last `--lookback-days` that are missing from
silver.meter_readings, using the same validation/enrichment logic as the
streaming path so a late-arriving invalid record is quarantined exactly
like an on-time one would be.

Idempotent by construction: every run re-derives quarantine_reasons from
scratch and MERGEs on natural keys, so re-running this job (e.g. after a
prior run's failure) never double-inserts or double-counts.
"""

import argparse
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.libs.common.units import to_liters
from src.libs.quality.expectations import with_quarantine_reasons


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog name for this environment."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=3,
        help=(
            "How many days of Bronze ingest_date partitions to re-scan. "
            "Must exceed the streaming watermark (default 24h) with slack "
            "for job-runtime delay."
        ),
    )
    parser.add_argument("--watermark-hours", type=int, default=24)
    parser.add_argument("--max-clock-skew-hours", type=int, default=1)
    parser.add_argument("--max-plausible-liters", type=float, default=1_000_000_000.0)
    return parser.parse_args(argv)


def _current_dim(spark: SparkSession, catalog: str, table_name: str) -> DataFrame:
    return spark.read.table(f"{catalog}.{table_name}").filter("is_current")


def build_candidate_readings(spark: SparkSession, catalog: str, lookback_days: int) -> DataFrame:
    """Bronze rows from the last `lookback_days` ingest_date partitions —
    the pool this job re-validates and reconciles into Silver/quarantine."""
    return spark.read.table(f"{catalog}.bronze.meter_telemetry").filter(
        F.col("ingest_date") >= F.date_sub(F.current_date(), lookback_days)
    )


def enrich_and_validate(
    bronze: DataFrame,
    spark: SparkSession,
    catalog: str,
    *,
    max_plausible_liters: float,
    max_clock_skew_hours: int,
) -> DataFrame:
    """Batch equivalent of the streaming pipeline's `stg_enriched_readings`
    (src/pipelines/silver/silver_meter_readings.py) — kept logically
    identical (same join keys, same helper functions) so a record is
    judged valid/invalid the same way regardless of which path processed
    it."""
    dim_meter = _current_dim(spark, catalog, "reference.dim_meter").select(
        F.col("meter_id"),
        F.col("customer_id").alias("ref_customer_id"),
        F.col("dma_id").alias("ref_meter_dma_id"),
        F.col("meter_type").alias("ref_meter_type"),
        F.col("meter_size_mm").alias("ref_meter_size_mm"),
        F.col("expected_unit").alias("ref_meter_expected_unit"),
        F.col("install_date").alias("ref_meter_install_date"),
        F.col("status").alias("ref_meter_status"),
    )
    dim_dma = _current_dim(spark, catalog, "reference.dim_dma").select(
        F.col("dma_id").alias("ref_dma_id"),
        F.col("dma_name").alias("ref_dma_name"),
        F.col("region").alias("ref_dma_region"),
        F.col("utc_offset_minutes").alias("ref_dma_utc_offset_minutes"),
    )

    enriched = (
        bronze.join(F.broadcast(dim_meter), on="meter_id", how="left")
        .join(F.broadcast(dim_dma), on=bronze["dma_id"] == F.col("ref_dma_id"), how="left")
        .withColumn("reading_value_liters", to_liters(F.col("reading_value"), F.col("unit")))
        .withColumn(
            "reading_local_timestamp",
            F.col("reading_timestamp")
            + F.make_interval(mins=F.coalesce(F.col("ref_dma_utc_offset_minutes"), F.lit(0))),
        )
    )
    return with_quarantine_reasons(
        enriched,
        max_plausible_liters=max_plausible_liters,
        max_clock_skew_hours=max_clock_skew_hours,
    )


_SILVER_COLUMNS = [
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
    "ref_customer_id",
    "ref_meter_dma_id",
    "ref_meter_type",
    "ref_meter_size_mm",
    "ref_dma_name",
    "ref_dma_region",
    "firmware_version",
    "sequence_no",
    "kafka_partition",
    "kafka_offset",
    "ingest_date",
]

_QUARANTINE_COLUMNS = [
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
]


def merge_valid_into_silver(spark: SparkSession, catalog: str, validated: DataFrame) -> None:
    valid = validated.filter("is_valid").select(*_SILVER_COLUMNS)
    valid.createOrReplaceTempView("_late_arrival_valid_readings")
    spark.sql(f"""
        MERGE INTO {catalog}.silver.meter_readings AS target
        USING _late_arrival_valid_readings AS source
        ON target.meter_id = source.meter_id
           AND target.reading_timestamp = source.reading_timestamp
        WHEN MATCHED AND source.ingest_timestamp > target.ingest_timestamp THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """)


def merge_invalid_into_quarantine(spark: SparkSession, catalog: str, validated: DataFrame) -> None:
    invalid = (
        validated.filter("NOT is_valid")
        .withColumn("quarantined_at", F.current_timestamp())
        .select(*_QUARANTINE_COLUMNS, "quarantined_at")
    )
    invalid.createOrReplaceTempView("_late_arrival_quarantine_candidates")
    # No natural single-column key exists on the quarantine log; dedup
    # against an existing (meter_id, reading_timestamp, kafka_offset) triple
    # so re-running this job never double-logs the same Bronze record.
    spark.sql(f"""
        MERGE INTO {catalog}.quarantine.silver_meter_readings_quarantine AS target
        USING _late_arrival_quarantine_candidates AS source
        ON target.meter_id <=> source.meter_id
           AND target.reading_timestamp <=> source.reading_timestamp
           AND target.kafka_offset <=> source.kafka_offset
        WHEN NOT MATCHED THEN INSERT *
        """)


def run(spark: SparkSession, args: argparse.Namespace) -> None:
    if args.lookback_days * 24 <= args.watermark_hours:
        raise ValueError(
            f"--lookback-days={args.lookback_days} (={args.lookback_days * 24}h) must exceed "
            f"--watermark-hours={args.watermark_hours}, or this job would re-scan a window "
            "narrower than what the streaming flow already covers, missing exactly the "
            "late arrivals it exists to catch."
        )
    candidates = build_candidate_readings(spark, args.catalog, args.lookback_days)
    validated = enrich_and_validate(
        candidates,
        spark,
        args.catalog,
        max_plausible_liters=args.max_plausible_liters,
        max_clock_skew_hours=args.max_clock_skew_hours,
    )
    merge_valid_into_silver(spark, args.catalog, validated)
    merge_invalid_into_quarantine(spark, args.catalog, validated)


if __name__ == "__main__":
    parsed_args = parse_args(sys.argv[1:])
    spark_session = SparkSession.builder.appName("silver_late_arrival_reconciliation").getOrCreate()
    run(spark_session, parsed_args)
