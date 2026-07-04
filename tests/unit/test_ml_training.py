"""Unit tests for src/ml/training/ — exercises each train() function
end-to-end (real Delta reads, real sklearn fit, real MLflow logging)
against local Delta tables and a local file-based MLflow tracking URI, with
register_model=False since Unity Catalog model registration requires a
real UC connection this sandbox doesn't have. Same `spark_catalog`
two/three-level-naming rationale as tests/unit/test_seed_reference_data.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import mlflow
import pytest

from src.ml.training import (
    train_anomaly_detection,
    train_demand_forecasting,
    train_leak_detection,
    train_predictive_maintenance,
)

CATALOG = "spark_catalog"


@pytest.fixture(autouse=True)
def _gold_and_reference_schemas(spark):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.gold")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.reference")


def _use_local_mlflow(tmp_path):
    # sqlite, not the plain file store: MLflow 3.x's file-based tracking
    # backend is in maintenance mode and rejects new stores unless
    # MLFLOW_ALLOW_FILE_STORE is set — sqlite is the currently-recommended
    # local backend and needs no such override.
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")


def test_train_leak_detection_runs_end_to_end(spark, tmp_path):
    _use_local_mlflow(tmp_path)

    rows = []
    start = datetime(2026, 1, 1, 3, 0, 0)
    for meter_i in range(10):
        for day in range(20):
            hour_start = start + timedelta(days=day)
            rows.append(
                (
                    f"MTR-{meter_i:03d}",
                    hour_start,
                    1.0,
                    2,
                    5.0 + meter_i * 0.1,
                    90,
                    80.0,
                    "DMA-001",
                    "North Zone 01",
                    f"CUST-{meter_i:03d}",
                    "RESIDENTIAL",
                    "RESIDENTIAL",
                )
            )
    df = spark.createDataFrame(
        rows,
        [
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
        ],
    )
    df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.gold.hourly_consumption")

    run_id, model = train_leak_detection.train(
        spark, catalog=CATALOG, experiment_path=str(tmp_path / "exp"), register_model=False
    )

    assert run_id is not None
    assert hasattr(model, "predict")


def test_train_demand_forecasting_runs_end_to_end(spark, tmp_path):
    _use_local_mlflow(tmp_path)

    rows = []
    for dma_i in range(5):
        for day in range(30):
            d = date(2026, 1, 1) + timedelta(days=day)
            rows.append((f"DMA-{dma_i:03d}", d, 1000.0 + day * 5.0 + dma_i * 50))
    df = spark.createDataFrame(rows, ["dma_id", "reading_date", "metered_consumption_liters"])
    df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.gold.dma_analytics")

    run_id, model = train_demand_forecasting.train(
        spark, catalog=CATALOG, experiment_path=str(tmp_path / "exp"), register_model=False
    )

    assert run_id is not None
    assert hasattr(model, "predict")


def test_train_anomaly_detection_runs_end_to_end(spark, tmp_path):
    _use_local_mlflow(tmp_path)

    rows = []
    for meter_i in range(10):
        for day in range(20):
            d = date(2026, 1, 1) + timedelta(days=day)
            trailing_avg = 100.0 if day >= 7 else None
            rows.append(
                (
                    f"MTR-{meter_i:03d}",
                    d,
                    100.0 + meter_i,
                    trailing_avg,
                    4,
                    90,
                    "DMA-001",
                    "RESIDENTIAL",
                    "RESIDENTIAL",
                )
            )
    df = spark.createDataFrame(
        rows,
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
    df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.gold.daily_usage")

    run_id, models = train_anomaly_detection.train(
        spark, catalog=CATALOG, experiment_path=str(tmp_path / "exp"), register_model=False
    )

    assert run_id is not None
    assert "RESIDENTIAL" in models


def test_train_predictive_maintenance_runs_end_to_end(spark, tmp_path):
    _use_local_mlflow(tmp_path)

    daily_rows = []
    for meter_i in range(5):
        for day in range(60):
            d = date(2026, 1, 1) + timedelta(days=day)
            battery = max(1, 100 - day * 2)
            daily_rows.append((f"MTR-{meter_i:03d}", d, battery, 1.0))
    daily_df = spark.createDataFrame(
        daily_rows, ["meter_id", "reading_date", "min_battery_pct", "consumption_liters"]
    )
    daily_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.gold.daily_usage")

    dim_meter_rows = [(f"MTR-{i:03d}", date(2020, 1, 1), "2.5.0", "ACTIVE", True) for i in range(5)]
    dim_meter_df = spark.createDataFrame(
        dim_meter_rows, ["meter_id", "install_date", "firmware_version", "status", "is_current"]
    )
    dim_meter_df.write.format("delta").mode("overwrite").saveAsTable(
        f"{CATALOG}.reference.dim_meter"
    )

    run_id, model = train_predictive_maintenance.train(
        spark, catalog=CATALOG, experiment_path=str(tmp_path / "exp"), register_model=False
    )

    assert run_id is not None
    assert hasattr(model, "predict")
