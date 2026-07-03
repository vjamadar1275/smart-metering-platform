"""Unit tests for src/libs/common/units.py."""

from __future__ import annotations

from src.libs.common.units import LITERS_PER_GALLON, to_liters


def test_liters_pass_through_unchanged(spark):
    df = spark.createDataFrame([(10.0, "LITERS")], ["value", "unit"])
    result = df.withColumn("out", to_liters(df["value"], df["unit"])).first()["out"]
    assert result == 10.0


def test_gallons_convert_to_liters(spark):
    df = spark.createDataFrame([(1.0, "GALLONS")], ["value", "unit"])
    result = df.withColumn("out", to_liters(df["value"], df["unit"])).first()["out"]
    assert abs(result - LITERS_PER_GALLON) < 1e-9


def test_cubic_meters_convert_to_liters(spark):
    df = spark.createDataFrame([(2.0, "CUBIC_METERS")], ["value", "unit"])
    result = df.withColumn("out", to_liters(df["value"], df["unit"])).first()["out"]
    assert result == 2000.0


def test_unrecognized_unit_yields_null(spark):
    df = spark.createDataFrame([(5.0, "IMPERIAL_GALLONS")], ["value", "unit"])
    result = df.withColumn("out", to_liters(df["value"], df["unit"])).first()["out"]
    assert result is None
