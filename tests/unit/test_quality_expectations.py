"""Unit tests for src/libs/quality/expectations.py's quarantine-reason logic.

Each test starts from `_valid_row()` — a record that passes every hard
rule — and mutates exactly one field, asserting the expected reason code
appears (and no others), so a future rule change that accidentally widens
or narrows another rule's condition is caught.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.libs.quality.expectations import SOFT_EXPECTATIONS, with_quarantine_reasons

_SCHEMA = StructType(
    [
        StructField("meter_id", StringType()),
        StructField("reading_timestamp", TimestampType()),
        StructField("reading_value", DoubleType()),
        StructField("unit", StringType()),
        StructField("parse_error", StringType()),
        StructField("battery_pct", IntegerType()),
        StructField("signal_quality", IntegerType()),
        StructField("ref_meter_status", StringType()),
        StructField("ref_meter_expected_unit", StringType()),
        StructField("ref_meter_install_date", DateType()),
        StructField("ref_dma_id", StringType()),
    ]
)
_SCHEMA_COLUMNS = [f.name for f in _SCHEMA.fields]


def _valid_row(**overrides):
    row = {
        "meter_id": "MTR-000001",
        "reading_timestamp": datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        "reading_value": 1234.5,
        "unit": "LITERS",
        "parse_error": None,
        "battery_pct": 80,
        "signal_quality": 90,
        "ref_meter_status": "ACTIVE",
        "ref_meter_expected_unit": "LITERS",
        "ref_meter_install_date": date(2021, 3, 1),
        "ref_dma_id": "DMA-001",
    }
    row.update(overrides)
    return tuple(row[c] for c in _SCHEMA_COLUMNS)


def _reasons_for(spark, **overrides):
    df = spark.createDataFrame([_valid_row(**overrides)], _SCHEMA)
    result = with_quarantine_reasons(df).first()
    return set(result["quarantine_reasons"])


def test_valid_row_has_no_reasons(spark):
    assert _reasons_for(spark) == set()
    df = spark.createDataFrame([_valid_row()], _SCHEMA)
    assert with_quarantine_reasons(df).first()["is_valid"] is True


def test_bronze_parse_error_is_quarantined(spark):
    assert "bronze_parse_error" in _reasons_for(spark, parse_error="avro_deserialization_failed")


def test_missing_required_fields_are_quarantined(spark):
    # meter_id=None with ref_meter_status still populated isn't realizable via
    # a real left join (a NULL key never matches), but this fixture only
    # overrides one field at a time — the join-consequence case is covered by
    # test_unknown_meter_is_quarantined instead.
    assert _reasons_for(spark, meter_id=None) == {"missing_meter_id"}
    assert _reasons_for(spark, reading_timestamp=None) == {"missing_reading_timestamp"}
    assert _reasons_for(spark, reading_value=None) == {"missing_reading_value"}


def test_negative_reading_is_quarantined(spark):
    assert _reasons_for(spark, reading_value=-1.0) == {"negative_reading"}


def test_implausible_magnitude_is_quarantined(spark):
    assert _reasons_for(spark, reading_value=1e12) == {"implausible_reading_magnitude"}


def test_invalid_unit_is_quarantined(spark):
    # FURLONGS also mismatches ref_meter_expected_unit (LITERS) — both fire.
    assert _reasons_for(spark, unit="FURLONGS") == {"invalid_unit", "unit_mismatch"}
    assert _reasons_for(spark, unit=None) == {"invalid_unit"}


def test_future_reading_timestamp_is_quarantined(spark):
    far_future = datetime.now(UTC) + timedelta(days=1)
    assert "reading_timestamp_in_future" in _reasons_for(spark, reading_timestamp=far_future)


def test_unknown_meter_is_quarantined(spark):
    assert _reasons_for(
        spark, ref_meter_status=None, ref_meter_expected_unit=None, ref_meter_install_date=None
    ) == {"unknown_meter_id"}


def test_decommissioned_meter_is_quarantined(spark):
    assert _reasons_for(spark, ref_meter_status="DECOMMISSIONED") == {"meter_not_active"}


def test_reading_before_install_is_quarantined(spark):
    assert _reasons_for(spark, reading_timestamp=datetime(2019, 1, 1, tzinfo=UTC)) == {
        "reading_before_install"
    }


def test_unit_mismatch_is_quarantined(spark):
    assert _reasons_for(spark, unit="GALLONS", ref_meter_expected_unit="LITERS") == {
        "unit_mismatch"
    }


def test_unknown_dma_is_quarantined(spark):
    assert _reasons_for(spark, ref_dma_id=None) == {"unknown_dma_id"}


def test_multiple_violations_all_recorded(spark):
    reasons = _reasons_for(spark, reading_value=-5.0, ref_dma_id=None)
    assert reasons == {"negative_reading", "unknown_dma_id"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("battery_pct", 150), ("signal_quality", -5)],
)
def test_soft_expectations_do_not_quarantine(spark, field, value):
    """battery_pct/signal_quality out of range is tracked via
    SOFT_EXPECTATIONS (Lakeflow metrics in the pipeline) but never
    quarantines a row — asserted here so the two rule sets can't drift
    apart silently."""
    assert field in " ".join(SOFT_EXPECTATIONS.values())
    assert _reasons_for(spark, **{field: value}) == set()
