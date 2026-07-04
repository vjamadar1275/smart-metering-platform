"""Per-meter leak-detection features (Phase 7), built from
`gold.hourly_consumption`.

`gold.dma_analytics` (Phase 5) already computes a *DMA-level* night-flow
rule (`night_flow_anomaly_flag`) — useful for the operational dashboard,
but coarse: a single leaking meter's signal is diluted across an entire
DMA's worth of other meters before it ever reaches that rule. This module
builds the finer-grained, *per-meter* features
`src/ml/training/train_leak_detection.py` trains an unsupervised anomaly
model on, so a leak can be attributed to roughly the right meter rather
than only "somewhere in this DMA."

Reuses the same night-flow window (`NIGHT_FLOW_START_HOUR`/`_END_HOUR`)
`src/libs/common/gold_transforms.py` already established for DMA-level
detection, so "night" means the same thing at both grains.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.libs.common.gold_transforms import NIGHT_FLOW_END_HOUR, NIGHT_FLOW_START_HOUR

TRAILING_WINDOW_DAYS = 14


def build_leak_detection_features(hourly_consumption: DataFrame) -> DataFrame:
    """One row per (meter_id, feature_date): that meter's average night-time
    flow rate, a trailing 14-day per-meter baseline, and the ratio between
    them — the input `train_leak_detection.py`'s IsolationForest scores.

    `night_flow_ratio` is NULL (not zero) when there's no positive
    baseline yet (a meter's first ~2 weeks) — the training script drops
    those rows rather than treating an undefined ratio as "not anomalous."
    """
    night_hours = hourly_consumption.where(
        (F.hour("hour_start") >= NIGHT_FLOW_START_HOUR)
        & (F.hour("hour_start") < NIGHT_FLOW_END_HOUR)
    )

    daily_night_flow = night_hours.groupBy(
        "meter_id", F.to_date("hour_start").alias("feature_date")
    ).agg(
        F.avg("avg_flow_rate_lpm").alias("avg_night_flow_lpm"),
        F.first("dma_id", ignorenulls=True).alias("dma_id"),
        F.first("meter_type", ignorenulls=True).alias("meter_type"),
    )

    trailing_window = (
        Window.partitionBy("meter_id")
        .orderBy("feature_date")
        .rowsBetween(-TRAILING_WINDOW_DAYS, -1)
    )
    with_baseline = daily_night_flow.withColumn(
        "trailing_14d_avg_night_flow_lpm", F.avg("avg_night_flow_lpm").over(trailing_window)
    )

    return with_baseline.withColumn(
        "night_flow_ratio",
        F.when(
            F.col("trailing_14d_avg_night_flow_lpm") > 0,
            F.col("avg_night_flow_lpm") / F.col("trailing_14d_avg_night_flow_lpm"),
        ),
    )
