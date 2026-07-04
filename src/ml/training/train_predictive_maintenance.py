"""Trains a predictive-maintenance classifier (gradient-boosted trees)
predicting whether a meter's battery will cross the low-battery threshold
within 30 days, on `src/ml/features/predictive_maintenance_features.py`,
tracked and registered via MLflow per ADR-0008/ADR-0012.

Predicts "battery will get low," not "meter will fail" — see that feature
module's docstring for why this narrower, defensible framing was chosen
over inventing failure labels this platform has no real record of.

Usage (Databricks Job task — see bundles/ml_training_jobs.yml):
    python -m src.ml.training.train_predictive_maintenance --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

from src.ml.features.predictive_maintenance_features import build_predictive_maintenance_features

NUMERIC_FEATURE_COLUMNS = ["min_battery_pct", "battery_trend_slope_per_day", "meter_age_days"]
CATEGORICAL_FEATURE_COLUMNS = ["firmware_version", "meter_status"]
TARGET_COLUMN = "label_low_battery_within_30d"
MODEL_NAME = "predictive_maintenance_model"
MIN_TRAINING_ROWS = 100
TEST_SIZE = 0.2


def train(
    spark: SparkSession,
    catalog: str,
    experiment_path: str,
    register_model: bool = True,
):
    daily_usage = spark.read.table(f"{catalog}.gold.daily_usage")
    dim_meter = spark.read.table(f"{catalog}.reference.dim_meter").where("is_current = true")

    features = build_predictive_maintenance_features(daily_usage, dim_meter).where(
        f"{TARGET_COLUMN} IS NOT NULL AND battery_trend_slope_per_day IS NOT NULL"
    )
    pdf = features.select(
        *NUMERIC_FEATURE_COLUMNS, *CATEGORICAL_FEATURE_COLUMNS, TARGET_COLUMN
    ).toPandas()

    if len(pdf) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Only {len(pdf)} labeled rows available (need >= {MIN_TRAINING_ROWS}) — "
            "gold.daily_usage needs at least ~44 days of history per meter (14-day "
            "trend window plus a 30-day label horizon) before this model's training "
            "data is meaningful."
        )

    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    encoded_categorical = encoder.fit_transform(pdf[CATEGORICAL_FEATURE_COLUMNS])
    for i, col in enumerate(CATEGORICAL_FEATURE_COLUMNS):
        pdf[f"{col}_encoded"] = encoded_categorical[:, i]
    model_features = NUMERIC_FEATURE_COLUMNS + [f"{c}_encoded" for c in CATEGORICAL_FEATURE_COLUMNS]

    y = pdf[TARGET_COLUMN].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        pdf[model_features], y, test_size=TEST_SIZE, random_state=42, stratify=y
    )

    mlflow.set_experiment(experiment_path)

    with mlflow.start_run(run_name="train_predictive_maintenance") as run:
        model = GradientBoostingClassifier(random_state=42, n_estimators=200, max_depth=3)
        model.fit(X_train, y_train)

        predictions = model.predict(X_test)
        precision = float(precision_score(y_test, predictions, zero_division=0))
        recall = float(recall_score(y_test, predictions, zero_division=0))
        f1 = float(f1_score(y_test, predictions, zero_division=0))

        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 3)
        mlflow.log_param("training_rows", len(X_train))
        mlflow.log_param("positive_rate", float(y.mean()))
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("f1", f1)

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
        default="/Shared/smart-metering-platform/predictive_maintenance",
    )
    args = parser.parse_args()

    mlflow.set_registry_uri("databricks-uc")
    spark = SparkSession.builder.getOrCreate()
    train(spark, catalog=args.catalog, experiment_path=args.experiment_path)


if __name__ == "__main__":
    main()
