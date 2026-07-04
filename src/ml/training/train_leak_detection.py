"""Trains an unsupervised leak-detection model (IsolationForest) on
per-meter night-flow features (`src/ml/features/leak_detection_features.py`),
tracked and registered via MLflow per ADR-0008/ADR-0012.

Unsupervised, not classification: this platform has no real confirmed-leak
ground-truth labels (see ADR-0012's open item) — IsolationForest flags
meter-days whose `[avg_night_flow_lpm, night_flow_ratio]` look unlike the
bulk of the training population, a reasonable proxy for "unusual night
flow" without requiring labels that don't exist.

Usage (Databricks Job task — see bundles/ml_training_jobs.yml):
    python -m src.ml.training.train_leak_detection --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.ensemble import IsolationForest

from src.libs.monitoring.logger import get_logger
from src.ml.features.leak_detection_features import build_leak_detection_features

FEATURE_COLUMNS = ["avg_night_flow_lpm", "night_flow_ratio"]
# Expected fraction of meter-days that are genuinely anomalous — informs
# IsolationForest's contamination parameter. Not tuned against real ground
# truth (none exists yet); a starting prior based on typical utility leak
# incidence rates, to be revisited once Phase 8 monitoring surfaces real
# flagged-vs-confirmed rates.
CONTAMINATION = 0.02
N_ESTIMATORS = 200
MODEL_NAME = "leak_detection_model"
MIN_TRAINING_ROWS = 50


def train(
    spark: SparkSession,
    catalog: str,
    experiment_path: str,
    register_model: bool = True,
):
    """Returns (run_id, model). `register_model=False` (used by tests) logs
    the run to whatever tracking URI is already configured but skips the
    Unity Catalog model registry step, which requires a real UC connection
    this repository's local test environment doesn't have.
    """
    logger = get_logger(pipeline="train_leak_detection", layer="ml", run_id="n/a")

    hourly = spark.read.table(f"{catalog}.gold.hourly_consumption")
    features = build_leak_detection_features(hourly).where("night_flow_ratio IS NOT NULL")
    pdf = features.select(*FEATURE_COLUMNS).toPandas()

    if len(pdf) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Only {len(pdf)} labeled feature rows available (need >= {MIN_TRAINING_ROWS}) — "
            "gold.hourly_consumption needs more history before this model's training data "
            "is meaningful."
        )

    mlflow.set_experiment(experiment_path)

    with mlflow.start_run(run_name="train_leak_detection") as run:
        model = IsolationForest(
            contamination=CONTAMINATION, random_state=42, n_estimators=N_ESTIMATORS
        )
        model.fit(pdf[FEATURE_COLUMNS])

        predictions = model.predict(pdf[FEATURE_COLUMNS])
        anomaly_scores = model.decision_function(pdf[FEATURE_COLUMNS])
        flagged_rate = float((predictions == -1).mean())

        mlflow.log_param("contamination", CONTAMINATION)
        mlflow.log_param("n_estimators", N_ESTIMATORS)
        mlflow.log_param("training_rows", len(pdf))
        mlflow.log_metric("flagged_rate", flagged_rate)
        mlflow.log_metric("mean_anomaly_score", float(anomaly_scores.mean()))

        signature = infer_signature(pdf[FEATURE_COLUMNS], predictions)
        mlflow.sklearn.log_model(
            model,
            name="model",
            signature=signature,
            registered_model_name=f"{catalog}.ml.{MODEL_NAME}" if register_model else None,
        )

        logger.info(f"Trained {MODEL_NAME} on {len(pdf)} rows, flagged_rate={flagged_rate:.4f}")
        return run.info.run_id, model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    parser.add_argument(
        "--experiment-path",
        default="/Shared/smart-metering-platform/leak_detection",
        help="MLflow experiment path (Databricks workspace path).",
    )
    args = parser.parse_args()

    mlflow.set_registry_uri("databricks-uc")
    spark = SparkSession.builder.getOrCreate()
    train(spark, catalog=args.catalog, experiment_path=args.experiment_path)


if __name__ == "__main__":
    main()
