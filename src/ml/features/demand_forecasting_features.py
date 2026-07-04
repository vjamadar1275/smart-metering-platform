"""Per-DMA demand-forecasting features (Phase 7), built from
`gold.dma_analytics`.

Forecasting at DMA grain (not per-meter) matches how a water utility
actually plans demand/supply — capacity and NRW decisions are made at the
DMA level, and per-meter forecasts would be both far noisier (a single
household's day-to-day usage is close to random) and unnecessary for that
decision. `src/ml/training/train_demand_forecasting.py` trains a
next-day regression model on the lag/calendar features this module builds.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def build_demand_forecasting_features(dma_analytics: DataFrame) -> DataFrame:
    """One row per (dma_id, reading_date) with lag-1/lag-7/trailing-7-day
    features and the next day's actual consumption as the training target
    (`target_next_day_liters`) — NULL for the most recent date per DMA
    (there is no "next day" yet), which the training script must drop
    before fitting.
    """
    by_date = Window.partitionBy("dma_id").orderBy("reading_date")
    trailing_7d = by_date.rowsBetween(-7, -1)

    with_lags = (
        dma_analytics.withColumn(
            "lag_1d_liters", F.lag("metered_consumption_liters", 1).over(by_date)
        )
        .withColumn("lag_7d_liters", F.lag("metered_consumption_liters", 7).over(by_date))
        .withColumn("trailing_7d_avg_liters", F.avg("metered_consumption_liters").over(trailing_7d))
        .withColumn("day_of_week", F.dayofweek("reading_date"))
        .withColumn("is_weekend", F.dayofweek("reading_date").isin(1, 7))
    )

    return with_lags.withColumn(
        "target_next_day_liters",
        F.lead("metered_consumption_liters", 1).over(by_date),
    ).select(
        "dma_id",
        "reading_date",
        "metered_consumption_liters",
        "lag_1d_liters",
        "lag_7d_liters",
        "trailing_7d_avg_liters",
        "day_of_week",
        "is_weekend",
        "target_next_day_liters",
    )
