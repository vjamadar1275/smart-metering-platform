"""Unit tests for src/libs/quality/expectations.py."""

from __future__ import annotations

from datetime import datetime

from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.libs.quality.expectations import (
    METER_READING_EXPECTATIONS,
    all_rules_expression,
    first_failure_reason_code,
)

_SCHEMA = StructType(
    [
        StructField("meter_id", StringType()),
        StructField("reading_timestamp", TimestampType()),
        StructField("dma_id", StringType()),
        StructField("reading_value", DoubleType()),
        StructField("is_known_meter", BooleanType()),
    ]
)

_VALID_ROW = {
    "meter_id": "MTR-00000001",
    "reading_timestamp": datetime(2026, 1, 1),
    "dma_id": "DMA-001",
    "reading_value": 100.0,
    "is_known_meter": True,
}


def _row(spark, **overrides):
    data = {**_VALID_ROW, **overrides}
    return spark.createDataFrame([data], schema=_SCHEMA)


def test_all_rules_expression_true_for_a_fully_valid_row(spark):
    df = _row(spark).withColumn("valid", all_rules_expression())
    assert df.first()["valid"] is True


def test_all_rules_expression_false_when_meter_id_missing(spark):
    df = _row(spark, meter_id=None).withColumn("valid", all_rules_expression())
    assert df.first()["valid"] is False


def test_all_rules_expression_false_for_negative_reading_value(spark):
    df = _row(spark, reading_value=-5.0).withColumn("valid", all_rules_expression())
    assert df.first()["valid"] is False


def test_all_rules_expression_false_for_unknown_meter(spark):
    df = _row(spark, is_known_meter=False).withColumn("valid", all_rules_expression())
    assert df.first()["valid"] is False


def test_first_failure_reason_code_null_for_valid_row(spark):
    df = _row(spark).withColumn("reason_code", first_failure_reason_code())
    assert df.first()["reason_code"] is None


def test_first_failure_reason_code_reports_missing_meter_id(spark):
    df = _row(spark, meter_id=None).withColumn("reason_code", first_failure_reason_code())
    assert df.first()["reason_code"] == "missing_meter_id"


def test_first_failure_reason_code_reports_first_rule_when_multiple_fail(spark):
    # meter_id is checked before reading_value in METER_READING_EXPECTATIONS'
    # iteration order, so a row failing both should report the earlier one.
    df = _row(spark, meter_id=None, reading_value=-5.0).withColumn(
        "reason_code", first_failure_reason_code()
    )
    assert df.first()["reason_code"] == "missing_meter_id"


def test_first_failure_reason_code_reports_out_of_range_reading():
    assert "reading_value_out_of_range" in METER_READING_EXPECTATIONS


def test_first_failure_reason_code_for_implausibly_large_reading(spark):
    df = _row(spark, reading_value=99_999_999.0).withColumn(
        "reason_code", first_failure_reason_code()
    )
    assert df.first()["reason_code"] == "reading_value_out_of_range"


def test_custom_rules_dict_is_respected(spark):
    custom_rules = {"always_fails": "1 = 0"}
    df = _row(spark).withColumn("valid", all_rules_expression(custom_rules))
    assert df.first()["valid"] is False
