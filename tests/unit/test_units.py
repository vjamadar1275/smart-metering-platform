"""Unit tests for src/libs/common/units.py's unit-normalization logic."""

from pyspark.sql import functions as F

from src.libs.common.units import LITERS_PER_CUBIC_METER, LITERS_PER_GALLON, to_liters


def test_to_liters_identity_for_liters(spark):
    df = spark.createDataFrame([(10.0, "LITERS")], ["reading_value", "unit"])
    result = df.withColumn("liters", to_liters(F.col("reading_value"), F.col("unit"))).first()
    assert result["liters"] == 10.0


def test_to_liters_converts_gallons(spark):
    df = spark.createDataFrame([(10.0, "GALLONS")], ["reading_value", "unit"])
    result = df.withColumn("liters", to_liters(F.col("reading_value"), F.col("unit"))).first()
    assert result["liters"] == 10.0 * LITERS_PER_GALLON


def test_to_liters_converts_cubic_meters(spark):
    df = spark.createDataFrame([(2.0, "CUBIC_METERS")], ["reading_value", "unit"])
    result = df.withColumn("liters", to_liters(F.col("reading_value"), F.col("unit"))).first()
    assert result["liters"] == 2.0 * LITERS_PER_CUBIC_METER


def test_to_liters_null_for_unrecognized_unit(spark):
    df = spark.createDataFrame([(10.0, "FURLONGS")], ["reading_value", "unit"])
    result = df.withColumn("liters", to_liters(F.col("reading_value"), F.col("unit"))).first()
    assert result["liters"] is None
