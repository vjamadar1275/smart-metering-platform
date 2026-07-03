"""Unit tests for src/jobs/silver_late_arrival_reconciliation.py.

Exercises `_late_arriving_bronze_rows` (the anti-join that decides which
Bronze rows still need reconciling) directly against local Delta tables
under Spark's built-in `spark_catalog` (the only catalog name usable for a
real three-level `catalog.schema.table` reference without a Unity Catalog
connection) — same rationale as tests/unit/test_seed_reference_data.py for
why this doesn't go through the `main()` entry point. Each test overwrites
the shared `bronze`/`silver` schemas rather than using per-test schema
names, since tests run sequentially against the session-scoped `spark`
fixture.
"""

from __future__ import annotations

from datetime import date, datetime

from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.jobs.silver_late_arrival_reconciliation import _late_arriving_bronze_rows

CATALOG = "spark_catalog"

# Explicit schema: some tests supply an all-NULL `parse_error` column, which
# Spark's type inference from raw tuples cannot resolve on its own.
BRONZE_SCHEMA = StructType(
    [
        StructField("meter_id", StringType()),
        StructField("reading_timestamp", TimestampType()),
        StructField("ingest_timestamp", TimestampType()),
        StructField("reading_value", DoubleType()),
        StructField("unit", StringType()),
        StructField("flow_rate", DoubleType()),
        StructField("battery_pct", IntegerType()),
        StructField("signal_quality", IntegerType()),
        StructField("dma_id", StringType()),
        StructField("firmware_version", StringType()),
        StructField("sequence_no", IntegerType()),
        StructField("parse_error", StringType()),
        StructField("ingest_date", DateType()),
    ]
)


def _bronze_row(meter_id, reading_ts, parse_error=None, ingest_date=None):
    ts = datetime.fromisoformat(reading_ts)
    return (
        meter_id,
        ts,
        ts,
        100.0,
        "LITERS",
        1.0,
        90,
        80,
        "DMA-001",
        "2.5.0",
        1,
        parse_error,
        ingest_date or date.today(),
    )


def _reset_bronze_and_silver(spark, bronze_rows, silver_rows):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.bronze")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.silver")

    spark.createDataFrame(bronze_rows, schema=BRONZE_SCHEMA).write.format("delta").mode(
        "overwrite"
    ).option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.bronze.meter_telemetry")

    if silver_rows:
        silver_df = spark.createDataFrame(silver_rows, ["meter_id", "reading_timestamp"])
    else:
        silver_df = spark.createDataFrame([], "meter_id STRING, reading_timestamp TIMESTAMP")
    silver_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{CATALOG}.silver.meter_readings"
    )


def test_late_arriving_rows_excludes_rows_already_in_silver(spark):
    _reset_bronze_and_silver(
        spark,
        bronze_rows=[
            _bronze_row("MTR-001", "2026-01-01T00:00:00"),
            _bronze_row("MTR-002", "2026-01-01T00:15:00"),
        ],
        silver_rows=[("MTR-001", datetime.fromisoformat("2026-01-01T00:00:00"))],
    )

    result = _late_arriving_bronze_rows(spark, CATALOG, lookback_days=7)
    result_meter_ids = {row["meter_id"] for row in result.collect()}

    assert result_meter_ids == {"MTR-002"}


def test_late_arriving_rows_excludes_parse_failures(spark):
    _reset_bronze_and_silver(
        spark,
        bronze_rows=[
            _bronze_row("MTR-003", "2026-01-01T00:00:00"),
            _bronze_row(
                "MTR-004", "2026-01-01T00:15:00", parse_error="avro_deserialization_failed"
            ),
        ],
        silver_rows=[],
    )

    result = _late_arriving_bronze_rows(spark, CATALOG, lookback_days=7)
    result_meter_ids = {row["meter_id"] for row in result.collect()}

    assert result_meter_ids == {"MTR-003"}


def test_late_arriving_rows_excludes_rows_outside_lookback_window(spark):
    _reset_bronze_and_silver(
        spark,
        bronze_rows=[
            _bronze_row("MTR-005", "2026-01-01T00:00:00", ingest_date=date(2020, 1, 1)),
            _bronze_row("MTR-006", "2026-01-01T00:15:00"),
        ],
        silver_rows=[],
    )

    result = _late_arriving_bronze_rows(spark, CATALOG, lookback_days=7)
    result_meter_ids = {row["meter_id"] for row in result.collect()}

    assert result_meter_ids == {"MTR-006"}
