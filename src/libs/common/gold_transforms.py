"""Silver -> Gold aggregation logic (Phase 5).

Pure DataFrame -> DataFrame transforms, identically reusable by the
continuous Gold streaming pipeline (src/pipelines/gold/gold_hourly_consumption.py)
and the triggered/batch Gold pipeline
(src/pipelines/gold/gold_daily_marts.py) — the pipeline files themselves are
thin wrappers that read the right upstream table(s) and call these
functions, so the aggregation logic is unit-testable without a running
Lakeflow pipeline (see tests/unit/test_gold_transforms.py).

See docs/architecture/ARCHITECTURE.md#4-silver--gold and ADR-0011 for the
design (why hourly_consumption is streaming and the rest are triggered
batch; why dma_analytics' `estimated_supply_liters` is a documented proxy,
not real bulk-supply telemetry).
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# A reading with no rolling baseline yet (a meter's first week) or with a
# baseline of (near) zero can't produce a meaningful usage-anomaly ratio —
# both are excluded from anomaly_flag rather than reported as a spurious
# infinite/undefined spike.
MIN_BASELINE_LITERS_FOR_ANOMALY_CHECK = 1.0
USAGE_ANOMALY_MULTIPLIER = 3.0
LOW_BATTERY_THRESHOLD_PCT = 15
HIGH_USAGE_PERCENTILE_MULTIPLIER = 2.0
# Classic DMA leak-detection window: sustained non-zero flow at these hours
# indicates a leak rather than legitimate demand (see
# tools/mock_data_generator/generator.py's leak injection, which targets
# exactly this window).
NIGHT_FLOW_START_HOUR = 2
NIGHT_FLOW_END_HOUR = 4


def _carry_through_dims(group_cols: list[str], *extra_cols: str):
    """`F.first(col, ignorenulls=True)` for dimension columns that are
    constant within a group (e.g. every reading for one meter on one day
    shares the same dma_id) — cheap to carry through an aggregate without a
    second join back to the dimension tables.
    """
    return [F.first(c, ignorenulls=True).alias(c) for c in extra_cols if c not in group_cols]


def compute_hourly_consumption(readings: DataFrame) -> DataFrame:
    """Per-meter, per-hour volumetric usage (gold.hourly_consumption).

    `readings` is expected to already have a watermark applied by the
    caller when used on a streaming DataFrame — this function itself is
    watermark-agnostic (works identically in batch, which is what
    tests/unit/test_gold_transforms.py exercises).

    Consumption is `max - min` of the cumulative totalizer within the hour
    window, not a sum of deltas between consecutive readings: the totalizer
    itself is authoritative, and taking max-min is robust to a missing
    interior reading in a way that summing consecutive deltas is not.
    """
    windowed = readings.groupBy(
        F.col("meter_id"), F.window(F.col("reading_timestamp"), "1 hour").alias("hour_window")
    ).agg(
        (F.max("reading_value_liters") - F.min("reading_value_liters")).alias("consumption_liters"),
        F.count(F.lit(1)).alias("reading_count"),
        F.avg("flow_rate").alias("avg_flow_rate_lpm"),
        F.min("battery_pct").alias("min_battery_pct"),
        F.avg("signal_quality").alias("avg_signal_quality"),
        *_carry_through_dims(
            ["meter_id"], "dma_id", "dma_name", "customer_id", "meter_type", "account_type"
        ),
    )
    return windowed.select(
        "meter_id",
        F.col("hour_window.start").alias("hour_start"),
        F.col("hour_window.end").alias("hour_end"),
        "consumption_liters",
        "reading_count",
        "avg_flow_rate_lpm",
        "min_battery_pct",
        "avg_signal_quality",
        "dma_id",
        "dma_name",
        "customer_id",
        "meter_type",
        "account_type",
    )


def compute_daily_usage(readings: DataFrame) -> DataFrame:
    """Per-meter, per-day usage with a trailing-7-day baseline and a simple
    usage-anomaly flag (gold.daily_usage).

    The anomaly flag is a coarse "consumption is unusually high vs. this
    meter's own recent history" signal for the operational dashboard, not a
    substitute for Phase 7's Mosaic AI leak-detection model — it exists so
    Gold has a usable anomaly signal from Phase 5 onward, before Phase 7's
    model exists.
    """
    daily = readings.groupBy("meter_id", "reading_date").agg(
        (F.max("reading_value_liters") - F.min("reading_value_liters")).alias("consumption_liters"),
        F.count(F.lit(1)).alias("reading_count"),
        F.min("battery_pct").alias("min_battery_pct"),
        *_carry_through_dims(
            ["meter_id", "reading_date"],
            "dma_id",
            "dma_name",
            "customer_id",
            "account_type",
            "meter_type",
        ),
    )

    trailing_window = Window.partitionBy("meter_id").orderBy("reading_date").rowsBetween(-7, -1)
    with_baseline = daily.withColumn(
        "trailing_7d_avg_liters", F.avg("consumption_liters").over(trailing_window)
    )

    return with_baseline.withColumn(
        "usage_anomaly_flag",
        F.when(
            (F.col("trailing_7d_avg_liters") >= MIN_BASELINE_LITERS_FOR_ANOMALY_CHECK)
            & (
                F.col("consumption_liters")
                > F.col("trailing_7d_avg_liters") * USAGE_ANOMALY_MULTIPLIER
            ),
            True,
        ).otherwise(False),
    )


def compute_dma_night_flow(readings: DataFrame) -> DataFrame:
    """Per-DMA, per-day average flow rate during the {NIGHT_FLOW_START_HOUR}
    -{NIGHT_FLOW_END_HOUR}h window — the leak-indicator input to
    compute_dma_analytics. Sustained elevated night flow across a DMA's
    meters (as opposed to one meter) suggests a distribution-network leak
    rather than a single customer's plumbing issue.
    """
    night_readings = readings.where(
        (F.hour("reading_timestamp") >= NIGHT_FLOW_START_HOUR)
        & (F.hour("reading_timestamp") < NIGHT_FLOW_END_HOUR)
    )
    return night_readings.groupBy("dma_id", "reading_date").agg(
        F.avg("flow_rate").alias("avg_night_flow_lpm"),
        F.countDistinct("meter_id").alias("night_flow_meter_count"),
    )


def compute_dma_analytics(
    daily_usage: DataFrame, night_flow: DataFrame, dim_dma: DataFrame
) -> DataFrame:
    """District Meter Area balance and leak indicators (gold.dma_analytics).

    `estimated_supply_liters` is a **documented proxy**, not real bulk/
    production-meter telemetry: this platform ingests customer smart meter
    readings only (see schemas/avro/meter_telemetry.avsc) and has no bulk
    supply-meter/SCADA data source integrated yet. It is derived from
    `reference.dim_dma.target_nrw_pct` (metered / (1 - target_nrw_pct/100))
    so the shape of the non-revenue-water calculation is real and usable
    for demos/testing, but the number itself should not be treated as a
    genuine water-balance audit figure until a real bulk-supply integration
    exists — tracked as an open item in ADR-0011.

    `night_flow_anomaly_flag`, by contrast, uses only real metered data
    (see compute_dma_night_flow) and is a legitimate leak indicator on its
    own, independent of the supply-data gap.
    """
    dma_daily_consumption = daily_usage.groupBy("dma_id", "reading_date").agg(
        F.sum("consumption_liters").alias("metered_consumption_liters"),
        F.countDistinct("meter_id").alias("active_meter_count"),
        F.sum(F.col("usage_anomaly_flag").cast("int")).alias("meters_with_usage_anomaly"),
    )

    joined = dma_daily_consumption.join(night_flow, on=["dma_id", "reading_date"], how="left").join(
        dim_dma.select("dma_id", "dma_name", "zone", "population_served", "target_nrw_pct"),
        on="dma_id",
        how="left",
    )

    with_supply = joined.withColumn(
        "estimated_supply_liters",
        F.col("metered_consumption_liters") / (1 - F.col("target_nrw_pct") / 100.0),
    )
    with_nrw = with_supply.withColumn(
        "non_revenue_water_liters",
        F.col("estimated_supply_liters") - F.col("metered_consumption_liters"),
    ).withColumn(
        "non_revenue_water_pct",
        F.col("non_revenue_water_liters") / F.col("estimated_supply_liters") * 100.0,
    )

    trailing_window = Window.partitionBy("dma_id").orderBy("reading_date").rowsBetween(-14, -1)
    with_night_baseline = with_nrw.withColumn(
        "trailing_14d_avg_night_flow_lpm", F.avg("avg_night_flow_lpm").over(trailing_window)
    )

    return with_night_baseline.withColumn(
        "night_flow_anomaly_flag",
        F.when(
            F.col("trailing_14d_avg_night_flow_lpm").isNotNull()
            & (F.col("trailing_14d_avg_night_flow_lpm") > 0)
            & (F.col("avg_night_flow_lpm") > F.col("trailing_14d_avg_night_flow_lpm") * 2.0),
            True,
        ).otherwise(False),
    ).select(
        "dma_id",
        "dma_name",
        "zone",
        "reading_date",
        "population_served",
        "active_meter_count",
        "metered_consumption_liters",
        "target_nrw_pct",
        "estimated_supply_liters",
        "non_revenue_water_liters",
        "non_revenue_water_pct",
        "avg_night_flow_lpm",
        "trailing_14d_avg_night_flow_lpm",
        "night_flow_anomaly_flag",
        "meters_with_usage_anomaly",
    )


def compute_customer_analytics(daily_usage: DataFrame) -> DataFrame:
    """Customer-level usage trends and billing-relevant aggregates
    (gold.customer_analytics), rolled up from gold.daily_usage rather than
    re-reading raw Silver — daily_usage already computed the authoritative
    per-meter daily delta, so summing it per customer avoids recomputing
    (and risking a drift in) the same number twice.
    """
    daily_by_customer = daily_usage.groupBy("customer_id", "reading_date").agg(
        F.sum("consumption_liters").alias("consumption_liters"),
        F.countDistinct("meter_id").alias("meter_count"),
        *_carry_through_dims(["customer_id", "reading_date"], "account_type"),
    )

    recent_7d = Window.partitionBy("customer_id").orderBy("reading_date").rowsBetween(-6, 0)
    prior_7d = Window.partitionBy("customer_id").orderBy("reading_date").rowsBetween(-13, -7)
    rolling_30d = Window.partitionBy("customer_id").orderBy("reading_date").rowsBetween(-29, 0)

    with_rolling = (
        daily_by_customer.withColumn(
            "rolling_30d_avg_liters", F.avg("consumption_liters").over(rolling_30d)
        )
        .withColumn("recent_7d_avg_liters", F.avg("consumption_liters").over(recent_7d))
        .withColumn("prior_7d_avg_liters", F.avg("consumption_liters").over(prior_7d))
    )

    with_trend = with_rolling.withColumn(
        "trend_direction",
        F.when(F.col("prior_7d_avg_liters").isNull(), F.lit("INSUFFICIENT_HISTORY"))
        .when(
            F.col("recent_7d_avg_liters") > F.col("prior_7d_avg_liters") * 1.1, F.lit("INCREASING")
        )
        .when(
            F.col("recent_7d_avg_liters") < F.col("prior_7d_avg_liters") * 0.9, F.lit("DECREASING")
        )
        .otherwise(F.lit("STABLE")),
    )

    return with_trend.withColumn(
        "high_usage_flag",
        F.when(
            F.col("rolling_30d_avg_liters").isNotNull()
            & (
                F.col("consumption_liters")
                > F.col("rolling_30d_avg_liters") * HIGH_USAGE_PERCENTILE_MULTIPLIER
            ),
            True,
        ).otherwise(False),
    )


def compute_operational_dashboard(
    readings_today: DataFrame, quarantine_today: DataFrame, dma_analytics_today: DataFrame
) -> DataFrame:
    """Fleet-health snapshot for the operations team (gold.operational_dashboard):
    today's ingestion volume, low-battery meters needing a truck roll,
    quarantine rate (a data-quality health signal), and DMA leak-flag count.
    One row per pipeline run.
    """
    fleet_stats = readings_today.agg(
        F.countDistinct("meter_id").alias("active_meter_count"),
        F.count(F.lit(1)).alias("readings_ingested"),
        F.sum((F.col("battery_pct") < LOW_BATTERY_THRESHOLD_PCT).cast("int")).alias(
            "low_battery_reading_count"
        ),
    )
    quarantine_stats = quarantine_today.agg(F.count(F.lit(1)).alias("quarantined_count"))
    leak_stats = dma_analytics_today.agg(
        F.sum(F.col("night_flow_anomaly_flag").cast("int")).alias("dma_leak_flag_count")
    )

    combined = fleet_stats.crossJoin(quarantine_stats).crossJoin(leak_stats)
    return combined.withColumn(
        "quarantine_rate_pct",
        F.when(
            (F.col("readings_ingested") + F.col("quarantined_count")) > 0,
            F.col("quarantined_count")
            / (F.col("readings_ingested") + F.col("quarantined_count"))
            * 100.0,
        ).otherwise(F.lit(0.0)),
    ).withColumn("as_of", F.current_timestamp())


def compute_executive_dashboard(
    daily_usage_today: DataFrame,
    dma_analytics_today: DataFrame,
    customer_analytics_today: DataFrame,
) -> DataFrame:
    """Top-line KPI mart for executive reporting (gold.executive_dashboard):
    total volume, systemwide non-revenue-water rate, volume by customer
    segment, and high-usage customer count. One row per day.
    """
    volume_by_segment = (
        daily_usage_today.groupBy("account_type")
        .agg(F.sum("consumption_liters").alias("segment_liters"))
        .groupBy()
        .pivot("account_type", ["RESIDENTIAL", "COMMERCIAL", "INDUSTRIAL", "UNKNOWN"])
        .agg(F.first("segment_liters"))
    )

    total_stats = daily_usage_today.agg(
        F.sum("consumption_liters").alias("total_consumption_liters"),
        F.countDistinct("customer_id").alias("total_customers"),
    )
    high_usage_stats = customer_analytics_today.agg(
        F.sum(F.col("high_usage_flag").cast("int")).alias("high_usage_customer_count")
    )
    nrw_stats = dma_analytics_today.agg(
        F.sum("non_revenue_water_liters").alias("total_non_revenue_water_liters"),
        F.sum("estimated_supply_liters").alias("total_estimated_supply_liters"),
        F.sum(F.col("night_flow_anomaly_flag").cast("int")).alias("dma_leak_flag_count"),
    )

    combined = (
        total_stats.crossJoin(high_usage_stats).crossJoin(nrw_stats).crossJoin(volume_by_segment)
    )
    return (
        combined.withColumn(
            "systemwide_nrw_pct",
            F.when(
                F.col("total_estimated_supply_liters") > 0,
                F.col("total_non_revenue_water_liters")
                / F.col("total_estimated_supply_liters")
                * 100.0,
            ).otherwise(F.lit(None).cast("double")),
        )
        .withColumnRenamed("RESIDENTIAL", "residential_liters")
        .withColumnRenamed("COMMERCIAL", "commercial_liters")
        .withColumnRenamed("INDUSTRIAL", "industrial_liters")
        .withColumnRenamed("UNKNOWN", "unknown_segment_liters")
        .withColumn("as_of", F.current_timestamp())
    )
