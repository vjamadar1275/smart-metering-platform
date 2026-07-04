"""Unit tests for src/ml/features/."""

from __future__ import annotations

from datetime import date, datetime

from src.ml.features.anomaly_detection_features import build_anomaly_detection_features
from src.ml.features.demand_forecasting_features import build_demand_forecasting_features
from src.ml.features.leak_detection_features import build_leak_detection_features
from src.ml.features.predictive_maintenance_features import build_predictive_maintenance_features

HOURLY_COLUMNS = [
    "meter_id",
    "hour_start",
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
]


def _hourly_row(meter_id, hour_start, avg_flow_rate_lpm, dma_id="DMA-001"):
    return (
        meter_id,
        datetime.fromisoformat(hour_start),
        1.0,
        4,
        avg_flow_rate_lpm,
        90,
        80.0,
        dma_id,
        "North Zone 01",
        "CUST-001",
        "RESIDENTIAL",
        "RESIDENTIAL",
    )


def test_leak_detection_features_flags_elevated_night_flow(spark):
    rows = []
    day0 = date(2026, 1, 1)
    for i in range(15):
        d = day0.fromordinal(day0.toordinal() + i)
        flow = 50.0 if i == 14 else 5.0  # baseline 5 lpm, spike on the last day
        rows.append(_hourly_row("MTR-LEAK", f"{d.isoformat()}T03:00:00", flow))
        rows.append(_hourly_row("MTR-NORMAL", f"{d.isoformat()}T03:00:00", 5.0))

    result = build_leak_detection_features(_hourly_df(spark, rows)).collect()
    leak_last_day = [
        r for r in result if r["meter_id"] == "MTR-LEAK" and r["feature_date"] == date(2026, 1, 15)
    ][0]
    normal_last_day = [
        r
        for r in result
        if r["meter_id"] == "MTR-NORMAL" and r["feature_date"] == date(2026, 1, 15)
    ][0]

    assert leak_last_day["night_flow_ratio"] > 5.0
    assert normal_last_day["night_flow_ratio"] is not None
    assert 0.5 < normal_last_day["night_flow_ratio"] < 1.5


def test_leak_detection_features_excludes_daytime_hours(spark):
    rows = [
        _hourly_row("MTR-001", "2026-01-01T12:00:00", 100.0),
    ]
    result = build_leak_detection_features(_hourly_df(spark, rows)).collect()
    assert result == []


def _hourly_df(spark, rows):
    return spark.createDataFrame(rows, HOURLY_COLUMNS)


def test_demand_forecasting_features_builds_lags_and_target(spark):
    rows = [("DMA-001", date(2026, 1, i), float(1000 + i * 10)) for i in range(1, 11)]
    df = spark.createDataFrame(rows, ["dma_id", "reading_date", "metered_consumption_liters"])

    result = build_demand_forecasting_features(df).orderBy("reading_date").collect()

    # Day 2 (index 1): lag_1d should equal day 1's consumption.
    day2 = result[1]
    assert day2["lag_1d_liters"] == rows[0][2]
    # Day 10: no next day, so target should be NULL.
    assert result[-1]["target_next_day_liters"] is None
    # Day 9: target should equal day 10's consumption.
    assert result[-2]["target_next_day_liters"] == rows[9][2]


def test_anomaly_detection_features_excludes_rows_without_baseline(spark):
    df = spark.createDataFrame(
        [
            (
                "MTR-001",
                date(2026, 1, 1),
                100.0,
                None,
                5,
                90,
                "DMA-001",
                "RESIDENTIAL",
                "RESIDENTIAL",
            ),
            (
                "MTR-001",
                date(2026, 1, 8),
                100.0,
                90.0,
                5,
                90,
                "DMA-001",
                "RESIDENTIAL",
                "RESIDENTIAL",
            ),
        ],
        [
            "meter_id",
            "reading_date",
            "consumption_liters",
            "trailing_7d_avg_liters",
            "reading_count",
            "min_battery_pct",
            "dma_id",
            "meter_type",
            "account_type",
        ],
    )

    result = build_anomaly_detection_features(df).collect()

    assert len(result) == 1
    assert abs(result[0]["consumption_ratio_to_baseline"] - (100.0 / 90.0)) < 1e-9


def test_predictive_maintenance_features_labels_declining_battery(spark):
    rows = []
    for i in range(45):
        d = date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i)
        battery = max(1, 100 - i * 3)  # drains ~3%/day, crosses 15% around day 28
        rows.append(("MTR-001", d, battery, 1.0))
    daily_usage = spark.createDataFrame(
        rows, ["meter_id", "reading_date", "min_battery_pct", "consumption_liters"]
    )
    dim_meter = spark.createDataFrame(
        [("MTR-001", date(2025, 1, 1), "2.5.0", "ACTIVE")],
        ["meter_id", "install_date", "firmware_version", "status"],
    )

    result = (
        build_predictive_maintenance_features(daily_usage, dim_meter)
        .orderBy("reading_date")
        .collect()
    )

    early_row = result[0]
    assert early_row["label_low_battery_within_30d"] is True
    assert early_row["meter_age_days"] > 0
    # regr_slope needs >= 2 trailing points; day 0 has only itself, so its
    # slope is NULL by construction, not a bug — check a later row instead.
    mid_row = result[5]
    assert mid_row["battery_trend_slope_per_day"] < 0

    late_row = result[-1]
    assert late_row["label_low_battery_within_30d"] is None  # not enough future history
