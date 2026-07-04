"""Per-meter general usage-anomaly features (Phase 7), built from
`gold.daily_usage`.

Distinct from `leak_detection_features.py`: leak detection specifically
targets the night-flow signature real leaks produce. This module feeds a
broader multivariate anomaly model
(`src/ml/training/train_anomaly_detection.py`) meant to also catch
patterns `gold.daily_usage.usage_anomaly_flag`'s simple upper-bound rule
(consumption > 3x trailing average) cannot by construction — most notably
a sudden *drop* toward zero (a stuck, bypassed, or failed meter), which is
just as operationally significant as a spike but invisible to a
"too high" threshold.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def build_anomaly_detection_features(daily_usage: DataFrame) -> DataFrame:
    """One row per (meter_id, reading_date): consumption relative to this
    meter's own trailing baseline, plus device-health signals (battery,
    reading count) that correlate with *why* a meter's readings might be
    anomalous (e.g. a low-battery meter dropping readings looks like a
    usage drop but is really a connectivity problem).

    Rows with no trailing baseline yet (`trailing_7d_avg_liters IS NULL`,
    a meter's first week — see gold_transforms.py:compute_daily_usage) are
    excluded: with no baseline, "ratio to baseline" is undefined, not zero.
    """
    with_ratio = daily_usage.where(F.col("trailing_7d_avg_liters").isNotNull()).withColumn(
        "consumption_ratio_to_baseline",
        F.when(
            F.col("trailing_7d_avg_liters") > 0,
            F.col("consumption_liters") / F.col("trailing_7d_avg_liters"),
        ).otherwise(F.lit(None)),
    )

    return with_ratio.where(F.col("consumption_ratio_to_baseline").isNotNull()).select(
        "meter_id",
        "reading_date",
        "consumption_liters",
        "trailing_7d_avg_liters",
        "consumption_ratio_to_baseline",
        "reading_count",
        "min_battery_pct",
        "dma_id",
        "meter_type",
        "account_type",
    )
