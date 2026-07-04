"""Per-meter predictive-maintenance features and training label (Phase 7),
built from `gold.daily_usage` joined against `reference.dim_meter`.

Predicts whether a meter's battery will cross the low-battery threshold
(`LOW_BATTERY_THRESHOLD_PCT`, reused from
`src/libs/common/gold_transforms.py`) within the next
`LABEL_HORIZON_DAYS` — a proxy for "this meter needs a truck roll soon."
There is no real historical failure/replacement log in this platform (see
ADR-0012's open item), so the training label is derived purely from each
meter's own future battery trajectory in the historical data, not from any
invented failure record — a legitimate technique, but the resulting model
predicts "battery will get low," not "will actually fail," which is a
narrower and more defensible claim.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from src.libs.common.gold_transforms import LOW_BATTERY_THRESHOLD_PCT

BATTERY_TREND_WINDOW_DAYS = 14
LABEL_HORIZON_DAYS = 30


def build_predictive_maintenance_features(
    daily_usage: DataFrame, dim_meter: DataFrame
) -> DataFrame:
    """One row per (meter_id, reading_date): current battery level, a
    14-day battery trend slope (negative = draining), meter age, and
    `label_low_battery_within_30d` — NULL wherever fewer than
    `LABEL_HORIZON_DAYS` of future history exist for that meter/date (the
    label is unknowable yet, not "false"). Training scripts must drop
    NULL-labeled rows; scoring/inference should keep them (there's no
    future to look ahead to at serving time either).
    """
    with_day_index = daily_usage.withColumn("day_index", F.unix_date("reading_date"))

    trend_window = (
        Window.partitionBy("meter_id")
        .orderBy("day_index")
        .rowsBetween(-BATTERY_TREND_WINDOW_DAYS, 0)
    )
    with_trend = with_day_index.withColumn(
        "battery_trend_slope_per_day",
        F.expr("regr_slope(min_battery_pct, day_index)").over(trend_window),
    )

    # Label: does battery_pct drop below the threshold at any point in the
    # next LABEL_HORIZON_DAYS? Implemented as a forward-looking MIN over a
    # leading window — if that forward minimum is below the threshold, the
    # meter crosses it within the horizon.
    forward_window = (
        Window.partitionBy("meter_id").orderBy("day_index").rowsBetween(1, LABEL_HORIZON_DAYS)
    )
    with_label = with_trend.withColumn(
        "_forward_min_battery_pct", F.min("min_battery_pct").over(forward_window)
    ).withColumn("_forward_row_count", F.count("min_battery_pct").over(forward_window))
    labeled = with_label.withColumn(
        "label_low_battery_within_30d",
        F.when(
            F.col("_forward_row_count") >= LABEL_HORIZON_DAYS,
            F.col("_forward_min_battery_pct") < LOW_BATTERY_THRESHOLD_PCT,
        ),
    )

    with_meter_age = labeled.join(
        dim_meter.select(
            "meter_id", "install_date", "firmware_version", F.col("status").alias("meter_status")
        ),
        on="meter_id",
        how="left",
    ).withColumn("meter_age_days", F.datediff(F.col("reading_date"), F.col("install_date")))

    return with_meter_age.select(
        "meter_id",
        "reading_date",
        "min_battery_pct",
        "battery_trend_slope_per_day",
        "meter_age_days",
        "firmware_version",
        "meter_status",
        "label_low_battery_within_30d",
    )
