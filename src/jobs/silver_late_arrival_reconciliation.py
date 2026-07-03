"""Nightly batch reconciliation for meter readings that arrive after
Silver's streaming watermark has already closed.

`src/pipelines/silver/silver_meter_readings.py` applies a 24-hour watermark
on `reading_timestamp` so its MERGE-based dedup (Lakeflow AUTO CDC) can
bound streaming state; Structured Streaming drops state for events older
than the watermark, so a reading that arrives more than 24 hours after its
own `reading_timestamp` (a meter reconnecting after an extended
connectivity gap) never reaches that streaming MERGE. This job is what
actually lands it — not dropping it — per
docs/architecture/ARCHITECTURE.md#3-bronze--silver ("Watermarking & late
arrival").

A plain scheduled batch Databricks Job task (src/jobs/, not a Lakeflow
pipeline — see bundles/silver_late_arrival_reconciliation_job.yml for the
daily schedule and ADR-0003's consequence on why non-continuous logic lives
outside Lakeflow), reusing the exact same enrichment/expectations logic as
the streaming pipeline (src/libs/common/enrichment.py,
src/libs/quality/expectations.py) so a late-arriving reading is validated
identically to an on-time one.

Usage (as a Databricks Job task):
    python -m src.jobs.silver_late_arrival_reconciliation \\
        --catalog smartmeter_dev --lookback-days 7 --run-id <job-run-id>
"""

from __future__ import annotations

import argparse

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.libs.common.enrichment import REQUIRED_READING_COLUMNS, enrich_meter_readings
from src.libs.io.reference_data import read_current_scd2_dimension, read_dma_dimension
from src.libs.monitoring.logger import get_logger
from src.libs.quality.expectations import (
    all_rules_expression,
    first_failure_reason_code,
)

DEFAULT_LOOKBACK_DAYS = 7


def _late_arriving_bronze_rows(spark: SparkSession, catalog: str, lookback_days: int) -> DataFrame:
    """Bronze rows within the lookback window that aren't in Silver yet —
    either genuinely late arrivals the streaming watermark missed, or rows
    a previous reconciliation run already would have caught (the anti-join
    makes re-running this job for overlapping windows idempotent).
    """
    bronze = (
        spark.read.table(f"{catalog}.bronze.meter_telemetry")
        .where(f"parse_error IS NULL AND ingest_date >= date_sub(current_date(), {lookback_days})")
        .select(*REQUIRED_READING_COLUMNS)
    )
    silver_keys = spark.read.table(f"{catalog}.silver.meter_readings").select(
        "meter_id", "reading_timestamp"
    )
    return bronze.join(silver_keys, on=["meter_id", "reading_timestamp"], how="left_anti")


def reconcile_late_arrivals(
    spark: SparkSession, catalog: str, lookback_days: int, run_id: str
) -> None:
    logger = get_logger(
        pipeline="silver_late_arrival_reconciliation", layer="silver", run_id=run_id
    )

    candidates = _late_arriving_bronze_rows(spark, catalog, lookback_days)
    dim_meter = read_current_scd2_dimension(spark, f"{catalog}.reference.dim_meter")
    dim_customer = read_current_scd2_dimension(spark, f"{catalog}.reference.dim_customer")
    dim_dma = read_dma_dimension(spark, f"{catalog}.reference.dim_dma")
    enriched = enrich_meter_readings(candidates, dim_meter, dim_customer, dim_dma).cache()

    valid = enriched.where(all_rules_expression())
    invalid = (
        enriched.where(~all_rules_expression())
        .withColumn("reason_code", first_failure_reason_code())
        .withColumn("quarantined_at", F.current_timestamp())
    )

    valid_count = valid.count()
    invalid_count = invalid.count()

    if valid_count > 0:
        # Two concurrent writers to silver.meter_readings (this batch MERGE
        # and the streaming AUTO CDC flow) can hit a Delta concurrent-write
        # conflict; scheduling this job at a low-traffic hour (see the
        # bundle's cron schedule) minimizes but doesn't eliminate that —
        # accepted as an operational reality, addressed by the job's retry
        # policy rather than application-level conflict handling.
        target = DeltaTable.forName(spark, f"{catalog}.silver.meter_readings")
        (
            target.alias("t")
            .merge(
                valid.alias("s"),
                "t.meter_id = s.meter_id AND t.reading_timestamp = s.reading_timestamp",
            )
            .whenNotMatchedInsertAll()
            .execute()
        )

    if invalid_count > 0:
        invalid.write.format("delta").mode("append").saveAsTable(
            f"{catalog}.quarantine.silver_meter_readings"
        )

    enriched.unpersist()
    logger.info(
        f"Late-arrival reconciliation: {valid_count} merged into Silver, "
        f"{invalid_count} quarantined, lookback={lookback_days}d."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument(
        "--run-id", default="local", help="Databricks Job run ID, for log correlation."
    )
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    reconcile_late_arrivals(
        spark, catalog=args.catalog, lookback_days=args.lookback_days, run_id=args.run_id
    )


if __name__ == "__main__":
    main()
