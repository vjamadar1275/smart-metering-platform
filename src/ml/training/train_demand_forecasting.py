"""Trains a next-day DMA demand-forecasting model (gradient-boosted trees
on lag/calendar features, `src/ml/features/demand_forecasting_features.py`),
tracked and registered via MLflow per ADR-0008/ADR-0012.

A single model across all DMAs (`dma_id` is a categorical feature) rather
than one model per DMA: with ~20 DMAs and a still-growing history in this
platform's synthetic data, per-DMA models would each be trained on too
little data to be meaningful — pooling lets the model learn shared
demand-pattern structure (day-of-week seasonality, autocorrelation) across
DMAs while `dma_id` still lets it distinguish DMA-specific baselines.

Usage (Databricks Job task — see bundles/ml_training_jobs.yml):
    python -m src.ml.training.train_demand_forecasting --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse

import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

FEATURE_COLUMNS = [
    "dma_id",
    "lag_1d_liters",
    "lag_7d_liters",
    "trailing_7d_avg_liters",
    "day_of_week",
    "is_weekend",
]
TARGET_COLUMN = "target_next_day_liters"
MODEL_NAME = "demand_forecasting_model"
MIN_TRAINING_ROWS = 100
TEST_SIZE = 0.2


def train(
    spark: SparkSession,
    catalog: str,
    experiment_path: str,
    register_model: bool = True,
):
    from src.ml.features.demand_forecasting_features import build_demand_forecasting_features

    dma_analytics = spark.read.table(f"{catalog}.gold.dma_analytics")
    features = build_demand_forecasting_features(dma_analytics).where(
        f"{TARGET_COLUMN} IS NOT NULL AND lag_1d_liters IS NOT NULL AND lag_7d_liters IS NOT NULL"
    )
    pdf = features.select(*FEATURE_COLUMNS, TARGET_COLUMN).toPandas()

    if len(pdf) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Only {len(pdf)} labeled rows available (need >= {MIN_TRAINING_ROWS}) — "
            "gold.dma_analytics needs at least ~8 days of history per DMA (7-day lag "
            "plus a next-day target) before this model's training data is meaningful."
        )

    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    pdf["dma_id_encoded"] = encoder.fit_transform(pdf[["dma_id"]])
    model_features = ["dma_id_encoded"] + [c for c in FEATURE_COLUMNS if c != "dma_id"]

    X_train, X_test, y_train, y_test = train_test_split(
        pdf[model_features], pdf[TARGET_COLUMN], test_size=TEST_SIZE, random_state=42
    )

    mlflow.set_experiment(experiment_path)

    with mlflow.start_run(run_name="train_demand_forecasting") as run:
        model = GradientBoostingRegressor(random_state=42, n_estimators=200, max_depth=3)
        model.fit(X_train, y_train)

        predictions = model.predict(X_test)
        mae = float(np.mean(np.abs(predictions - y_test)))
        mape = float(np.mean(np.abs((predictions - y_test) / y_test.replace(0, np.nan))) * 100)
        naive_mae = float(np.mean(np.abs(X_test["lag_1d_liters"] - y_test)))

        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 3)
        mlflow.log_param("training_rows", len(X_train))
        mlflow.log_metric("mae_liters", mae)
        mlflow.log_metric("mape_pct", mape)
        # The model should beat "tomorrow = today" — logged explicitly so a
        # a model that isn't actually adding value over the naive baseline
        # is visible in the MLflow run comparison, not just a standalone number.
        mlflow.log_metric("naive_baseline_mae_liters", naive_mae)

        signature = infer_signature(X_train, predictions)
        mlflow.sklearn.log_model(
            model,
            name="model",
            signature=signature,
            registered_model_name=f"{catalog}.ml.{MODEL_NAME}" if register_model else None,
        )

        return run.info.run_id, model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    parser.add_argument(
        "--experiment-path",
        default="/Shared/smart-metering-platform/demand_forecasting",
    )
    args = parser.parse_args()

    mlflow.set_registry_uri("databricks-uc")
    spark = SparkSession.builder.getOrCreate()
    train(spark, catalog=args.catalog, experiment_path=args.experiment_path)


if __name__ == "__main__":
    main()
