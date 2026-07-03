"""Unit tests for src/libs/common/gold_transforms.py."""

from __future__ import annotations

from datetime import date, datetime

from pyspark.sql import functions as F

from src.libs.common.gold_transforms import (
    compute_customer_analytics,
    compute_daily_usage,
    compute_dma_analytics,
    compute_dma_night_flow,
    compute_executive_dashboard,
    compute_hourly_consumption,
    compute_operational_dashboard,
)

READING_COLUMNS = [
    "meter_id",
    "reading_timestamp",
    "reading_value_liters",
    "flow_rate",
    "battery_pct",
    "signal_quality",
    "dma_id",
    "dma_name",
    "customer_id",
    "account_type",
    "meter_type",
    "reading_date",
]


def _reading(
    meter_id="MTR-001",
    ts="2026-01-01T00:00:00",
    value=0.0,
    flow_rate=1.0,
    battery_pct=90,
    signal_quality=80,
    dma_id="DMA-001",
    dma_name="North Zone 01",
    customer_id="CUST-001",
    account_type="RESIDENTIAL",
    meter_type="RESIDENTIAL",
):
    dt = datetime.fromisoformat(ts)
    return (
        meter_id,
        dt,
        value,
        flow_rate,
        battery_pct,
        signal_quality,
        dma_id,
        dma_name,
        customer_id,
        account_type,
        meter_type,
        dt.date(),
    )


def _readings_df(spark, rows):
    return spark.createDataFrame(rows, READING_COLUMNS)


def test_compute_hourly_consumption_sums_within_hour_window(spark):
    rows = [
        _reading(ts="2026-01-01T00:05:00", value=10.0),
        _reading(ts="2026-01-01T00:45:00", value=15.0),
        _reading(ts="2026-01-01T01:05:00", value=20.0),
    ]
    result = compute_hourly_consumption(_readings_df(spark, rows)).orderBy("hour_start").collect()

    assert len(result) == 2
    assert result[0]["consumption_liters"] == 5.0
    assert result[0]["reading_count"] == 2
    assert result[1]["consumption_liters"] == 0.0


def test_compute_daily_usage_max_minus_min_per_day(spark):
    rows = [
        _reading(ts="2026-01-01T00:00:00", value=100.0),
        _reading(ts="2026-01-01T23:00:00", value=130.0),
        _reading(ts="2026-01-02T00:00:00", value=130.0),
        _reading(ts="2026-01-02T23:00:00", value=145.0),
    ]
    result = compute_daily_usage(_readings_df(spark, rows)).orderBy("reading_date").collect()

    assert result[0]["reading_date"] == date(2026, 1, 1)
    assert result[0]["consumption_liters"] == 30.0
    assert result[1]["consumption_liters"] == 15.0


def test_compute_daily_usage_flags_anomaly_above_trailing_baseline(spark):
    rows = []
    day1 = date(2026, 1, 1)
    for i in range(8):
        d = day1.fromordinal(day1.toordinal() + i)
        value = 30.0 * (i + 1)  # cumulative totalizer, +30L/day baseline
        rows.append(_reading(ts=f"{d.isoformat()}T00:00:00", value=value))
        rows.append(
            _reading(ts=f"{d.isoformat()}T23:00:00", value=value + (300.0 if i == 7 else 30.0))
        )

    result = compute_daily_usage(_readings_df(spark, rows)).orderBy("reading_date").collect()
    last_day = result[-1]

    assert last_day["consumption_liters"] == 300.0
    assert last_day["usage_anomaly_flag"] is True
    assert result[0]["usage_anomaly_flag"] is False  # no trailing baseline yet


def test_compute_dma_night_flow_filters_to_night_window(spark):
    rows = [
        _reading(ts="2026-01-01T03:00:00", flow_rate=10.0),
        _reading(ts="2026-01-01T12:00:00", flow_rate=100.0),
    ]
    result = compute_dma_night_flow(_readings_df(spark, rows)).collect()

    assert len(result) == 1
    assert result[0]["avg_night_flow_lpm"] == 10.0


def test_compute_dma_analytics_estimates_supply_and_nrw(spark):
    daily_usage = spark.createDataFrame(
        [("MTR-001", date(2026, 1, 1), "DMA-001", 1000.0, False)],
        ["meter_id", "reading_date", "dma_id", "consumption_liters", "usage_anomaly_flag"],
    )
    night_flow = spark.createDataFrame(
        [("DMA-001", date(2026, 1, 1), 5.0, 3)],
        ["dma_id", "reading_date", "avg_night_flow_lpm", "night_flow_meter_count"],
    )
    dim_dma = spark.createDataFrame(
        [("DMA-001", "North Zone 01", "North", 10000, 20.0)],
        ["dma_id", "dma_name", "zone", "population_served", "target_nrw_pct"],
    )

    result = compute_dma_analytics(daily_usage, night_flow, dim_dma).first()

    assert result["metered_consumption_liters"] == 1000.0
    assert abs(result["estimated_supply_liters"] - 1250.0) < 1e-6
    assert abs(result["non_revenue_water_liters"] - 250.0) < 1e-6
    assert abs(result["non_revenue_water_pct"] - 20.0) < 1e-6


def _add_account_type(spark, rows):
    df = spark.createDataFrame(
        rows,
        [
            "meter_id",
            "reading_date",
            "customer_id",
            "dma_id",
            "consumption_liters",
            "usage_anomaly_flag",
        ],
    )
    return df.withColumn("account_type", F.lit("RESIDENTIAL"))


def test_customer_analytics_flags_high_usage_day(spark):
    rows = []
    for i in range(10):
        d = date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i)
        consumption = 500.0 if i == 9 else 50.0
        rows.append(("MTR-001", d, "CUST-001", "DMA-001", consumption, False))
    daily_usage = _add_account_type(spark, rows)

    result = compute_customer_analytics(daily_usage).orderBy("reading_date").collect()

    assert result[-1]["high_usage_flag"] is True
    assert result[0]["high_usage_flag"] is False


def test_compute_operational_dashboard_aggregates_fleet_health(spark):
    readings_today = _readings_df(
        spark,
        [
            _reading(meter_id="MTR-001", battery_pct=5),
            _reading(meter_id="MTR-002", battery_pct=90),
        ],
    )
    quarantine_today = spark.createDataFrame([("MTR-003",)], ["meter_id"])
    dma_analytics_today = spark.createDataFrame(
        [("DMA-001", True), ("DMA-002", False)], ["dma_id", "night_flow_anomaly_flag"]
    )

    result = compute_operational_dashboard(
        readings_today, quarantine_today, dma_analytics_today
    ).first()

    assert result["active_meter_count"] == 2
    assert result["low_battery_reading_count"] == 1
    assert result["quarantined_count"] == 1
    assert result["dma_leak_flag_count"] == 1


def test_compute_executive_dashboard_aggregates_top_line_kpis(spark):
    daily_usage_today = spark.createDataFrame(
        [
            ("CUST-001", "RESIDENTIAL", 100.0),
            ("CUST-002", "COMMERCIAL", 400.0),
        ],
        ["customer_id", "account_type", "consumption_liters"],
    )
    dma_analytics_today = spark.createDataFrame(
        [("DMA-001", 1250.0, 250.0, True)],
        [
            "dma_id",
            "estimated_supply_liters",
            "non_revenue_water_liters",
            "night_flow_anomaly_flag",
        ],
    )
    customer_analytics_today = spark.createDataFrame(
        [("CUST-001", False), ("CUST-002", True)], ["customer_id", "high_usage_flag"]
    )

    result = compute_executive_dashboard(
        daily_usage_today, dma_analytics_today, customer_analytics_today
    ).first()

    assert result["total_consumption_liters"] == 500.0
    assert result["residential_liters"] == 100.0
    assert result["commercial_liters"] == 400.0
    assert result["high_usage_customer_count"] == 1
    assert abs(result["systemwide_nrw_pct"] - 20.0) < 1e-6
