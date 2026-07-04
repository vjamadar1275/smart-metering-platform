"""Trains a general per-meter usage-anomaly model (IsolationForest,
multivariate) on `src/ml/features/anomaly_detection_features.py`, tracked
and registered via MLflow per ADR-0008/ADR-0012.

Unsupervised, like leak detection — see that training script's docstring
for why. Trained per `meter_type` segment (RESIDENTIAL/COMMERCIAL/INDUSTRIAL)
rather than one pooled model: a commercial meter's "normal" consumption
scale and variance are entirely different from a residential one's, so a
single pooled model would either be too loose for residential anomalies or
flag ordinary commercial variation as anomalous.

Usage (Databricks Job task — see bundles/ml_training_jobs.yml):
    python -m src.ml.training.train_anomaly_detection --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.ensemble import IsolationForest

from src.ml.features.anomaly_detection_features import build_anomaly_detection_features

FEATURE_COLUMNS = ["consumption_ratio_to_baseline", "reading_count", "min_battery_pct"]
CONTAMINATION = 0.03
N_ESTIMATORS = 200
MODEL_NAME = "anomaly_detection_model"
MIN_TRAINING_ROWS_PER_SEGMENT = 50


def train(
    spark: SparkSession,
    catalog: str,
    experiment_path: str,
    register_model: bool = True,
):
    daily_usage = spark.read.table(f"{catalog}.gold.daily_usage")
    features = build_anomaly_detection_features(daily_usage)
    pdf = features.select(*FEATURE_COLUMNS, "meter_type").toPandas()

    mlflow.set_experiment(experiment_path)

    models = {}
    with mlflow.start_run(run_name="train_anomaly_detection") as parent_run:
        for meter_type, segment in pdf.groupby("meter_type"):
            if len(segment) < MIN_TRAINING_ROWS_PER_SEGMENT:
                continue  # too little data for this segment yet; skip rather than train on noise

            with mlflow.start_run(run_name=f"segment_{meter_type}", nested=True):
                model = IsolationForest(
                    contamination=CONTAMINATION, random_state=42, n_estimators=N_ESTIMATORS
                )
                model.fit(segment[FEATURE_COLUMNS])
                predictions = model.predict(segment[FEATURE_COLUMNS])
                flagged_rate = float((predictions == -1).mean())

                mlflow.log_param("meter_type", meter_type)
                mlflow.log_param("training_rows", len(segment))
                mlflow.log_metric("flagged_rate", flagged_rate)

                signature = infer_signature(segment[FEATURE_COLUMNS], predictions)
                mlflow.sklearn.log_model(
                    model,
                    name="model",
                    signature=signature,
                    registered_model_name=(
                        f"{catalog}.ml.{MODEL_NAME}_{meter_type.lower()}"
                        if register_model
                        else None
                    ),
                )
                models[meter_type] = model

        mlflow.log_param("segments_trained", list(models.keys()))
        return parent_run.info.run_id, models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    parser.add_argument(
        "--experiment-path",
        default="/Shared/smart-metering-platform/anomaly_detection",
    )
    args = parser.parse_args()

    mlflow.set_registry_uri("databricks-uc")
    spark = SparkSession.builder.getOrCreate()
    train(spark, catalog=args.catalog, experiment_path=args.experiment_path)


if __name__ == "__main__":
    main()
