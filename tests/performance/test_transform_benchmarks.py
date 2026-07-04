"""Performance regression guards for the Gold/ML transform functions
(Phase 8), run against local PySpark at a larger synthetic scale than
tests/unit/'s small, hand-built fixtures.

These are not a substitute for real cluster-scale benchmarking (see
docs/guides/PERFORMANCE_GUIDE.md's sizing methodology, which needs a real
Databricks cluster and production-representative data volume this sandbox
doesn't have) — they exist to catch an accidental algorithmic regression
(e.g. an unintended row-by-row Python UDF replacing a vectorized
DataFrame operation, or a join that silently turns into a cross join)
locally and in CI, long before it would ever reach a real cluster.
Thresholds are deliberately generous (single-digit-to-tens-of-seconds on
single-executor local Spark for tens of thousands of rows) — they're a
regression tripwire, not a tuned performance target.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from src.libs.common.gold_transforms import compute_daily_usage, compute_hourly_consumption
from src.ml.features.predictive_maintenance_features import build_predictive_maintenance_features
from tools.mock_data_generator.generator import generate_meter_master

METER_COUNT = 500
DAY_COUNT = 90  # 500 meters x 90 days = 45,000 rows
MAX_SECONDS = 30.0


def _synthetic_readings(spark, meter_count: int, day_count: int):
    """One row per (meter, day), with the raw per-reading columns
    compute_daily_usage/build_predictive_maintenance_features actually
    read (battery_pct, not the output column name min_battery_pct) — a
    single row per day means max(reading_value_liters) - min(...) always
    evaluates to 0, which is fine here: these tests check scale/timing,
    not the aggregation's numeric correctness (tests/unit/test_gold_transforms.py
    already covers that with small, exact-value fixtures).
    """
    meters = generate_meter_master(meter_count, seed=1)
    start = date(2026, 1, 1)
    rows = [
        (
            m.meter_id,
            start + timedelta(days=d),
            100.0 + d * 1.5,
            max(1, 100 - d),
            m.dma_id,
            "Zone",
            m.customer_id,
            m.meter_type,
            m.meter_type,
        )
        for m in meters
        for d in range(day_count)
    ]
    return spark.createDataFrame(
        rows,
        [
            "meter_id",
            "reading_date",
            "reading_value_liters",
            "battery_pct",
            "dma_id",
            "dma_name",
            "customer_id",
            "account_type",
            "meter_type",
        ],
    )


def test_compute_daily_usage_completes_within_time_budget(spark):
    readings = _synthetic_readings(spark, METER_COUNT, DAY_COUNT)

    start = time.perf_counter()
    result_count = compute_daily_usage(readings).count()
    elapsed = time.perf_counter() - start

    assert result_count == METER_COUNT * DAY_COUNT
    assert elapsed < MAX_SECONDS, f"compute_daily_usage took {elapsed:.1f}s (budget {MAX_SECONDS}s)"


def test_compute_hourly_consumption_completes_within_time_budget(spark):
    meters = generate_meter_master(METER_COUNT, seed=2)
    start_ts = datetime(2026, 1, 1)
    hours = 24 * 7  # one week, hourly

    rows = [
        (
            m.meter_id,
            start_ts + timedelta(hours=h),
            50.0 + h,
            1.0,
            96,
            50,
            m.dma_id,
            "Zone",
            m.customer_id,
            m.meter_type,
            m.meter_type,
        )
        for m in meters
        for h in range(hours)
    ]
    readings = spark.createDataFrame(
        rows,
        [
            "meter_id",
            "reading_timestamp",
            "reading_value_liters",
            "flow_rate",
            "battery_pct",
            "signal_quality",
            "dma_id",
            "dma_name",
            "customer_id",
            "meter_type",
            "account_type",
        ],
    )

    start = time.perf_counter()
    result_count = compute_hourly_consumption(readings).count()
    elapsed = time.perf_counter() - start

    assert result_count > 0
    assert (
        elapsed < MAX_SECONDS
    ), f"compute_hourly_consumption took {elapsed:.1f}s (budget {MAX_SECONDS}s)"


def test_predictive_maintenance_features_window_functions_scale(spark):
    daily_usage_input = _synthetic_readings(spark, METER_COUNT, DAY_COUNT).withColumnRenamed(
        "battery_pct", "min_battery_pct"
    )
    meters = generate_meter_master(METER_COUNT, seed=1)
    dim_meter = spark.createDataFrame(
        [(m.meter_id, m.install_date, m.firmware_version, "ACTIVE") for m in meters],
        ["meter_id", "install_date", "firmware_version", "status"],
    )

    start = time.perf_counter()
    result_count = build_predictive_maintenance_features(daily_usage_input, dim_meter).count()
    elapsed = time.perf_counter() - start

    assert result_count == METER_COUNT * DAY_COUNT
    assert elapsed < MAX_SECONDS, (
        f"build_predictive_maintenance_features (regr_slope + forward-looking window) "
        f"took {elapsed:.1f}s (budget {MAX_SECONDS}s)"
    )
