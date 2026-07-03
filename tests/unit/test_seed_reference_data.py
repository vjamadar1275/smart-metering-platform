"""Unit tests for src/jobs/seed_reference_data.py.

Runs against local Delta tables in the default (non-Unity-Catalog) Spark
session's `spark_catalog` using two-level `database.table` names — the
three-level `catalog.schema.table` addressing this job uses in production
is a Unity Catalog feature with no local equivalent, so tests exercise
`_insert_missing_current_versions`/`_stamp_scd2_current_version` directly
against a plain database rather than the `main()` entry point.
"""

from __future__ import annotations

from src.jobs.seed_reference_data import (
    DIM_METER_SCHEMA,
    _insert_missing_current_versions,
    _stamp_scd2_current_version,
)


def _meter_rows(spark, meter_ids):
    from datetime import date

    return spark.createDataFrame(
        [
            (mid, "DMA-001", "CUST-001", "RESIDENTIAL", 15, date(2020, 1, 1), 29.0, -98.0, "ACTIVE")
            for mid in meter_ids
        ],
        schema=DIM_METER_SCHEMA,
    )


def test_stamp_scd2_current_version_sets_expected_columns(spark):
    df = _stamp_scd2_current_version(_meter_rows(spark, ["MTR-001"]))
    row = df.first()
    assert row["is_current"] is True
    assert row["effective_end_date"] is None
    assert row["effective_start_date"] is not None


def test_insert_missing_current_versions_creates_table_on_first_run(spark):
    spark.sql("CREATE DATABASE IF NOT EXISTS test_seed_reference_first_run")
    target = "test_seed_reference_first_run.dim_meter"

    source = _stamp_scd2_current_version(_meter_rows(spark, ["MTR-001", "MTR-002"]))
    _insert_missing_current_versions(spark, source, target, key_col="meter_id")

    assert spark.table(target).count() == 2


def test_insert_missing_current_versions_is_idempotent_and_additive(spark):
    spark.sql("CREATE DATABASE IF NOT EXISTS test_seed_reference_idempotent")
    target = "test_seed_reference_idempotent.dim_meter"

    first = _stamp_scd2_current_version(_meter_rows(spark, ["MTR-001", "MTR-002"]))
    _insert_missing_current_versions(spark, first, target, key_col="meter_id")

    # Re-running with an overlapping + one new key should not duplicate the
    # existing rows, and should add exactly the new one.
    second = _stamp_scd2_current_version(_meter_rows(spark, ["MTR-001", "MTR-002", "MTR-003"]))
    _insert_missing_current_versions(spark, second, target, key_col="meter_id")

    result = spark.table(target)
    assert result.count() == 3
    assert result.select("meter_id").distinct().count() == 3
