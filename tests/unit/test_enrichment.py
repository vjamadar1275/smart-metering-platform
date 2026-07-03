"""Unit tests for src/libs/common/enrichment.py."""

from __future__ import annotations

from datetime import datetime

from src.libs.common.enrichment import enrich_meter_readings

READING_COLUMNS = [
    "meter_id",
    "reading_timestamp",
    "ingest_timestamp",
    "reading_value",
    "unit",
    "flow_rate",
    "battery_pct",
    "signal_quality",
    "dma_id",
    "firmware_version",
    "sequence_no",
]


def _readings_df(spark, rows):
    return spark.createDataFrame(rows, READING_COLUMNS)


def _dim_meter_df(spark):
    return spark.createDataFrame(
        [("MTR-001", "CUST-001", "RESIDENTIAL", 15, "ACTIVE")],
        ["meter_id", "customer_id", "meter_type", "meter_size_mm", "status"],
    )


def _dim_customer_df(spark):
    return spark.createDataFrame(
        [("CUST-001", "Jane Doe", "RESIDENTIAL", "1 Main St")],
        ["customer_id", "account_name", "account_type", "service_address"],
    )


def _dim_dma_df(spark):
    return spark.createDataFrame(
        [("DMA-001", "North Zone 01", "North")],
        ["dma_id", "dma_name", "zone"],
    )


def _base_row(meter_id="MTR-001", dma_id="DMA-001", unit="LITERS", reading_value=100.0):
    ts = datetime(2026, 1, 1, 0, 0, 0)
    return (meter_id, ts, ts, reading_value, unit, 1.0, 90, 80, dma_id, "2.5.0", 1)


def test_known_meter_is_enriched_with_customer_and_dma_fields(spark):
    readings = _readings_df(spark, [_base_row()])
    result = enrich_meter_readings(
        readings, _dim_meter_df(spark), _dim_customer_df(spark), _dim_dma_df(spark)
    ).first()

    assert result["is_known_meter"] is True
    assert result["account_name"] == "Jane Doe"
    assert result["dma_name"] == "North Zone 01"
    assert result["meter_type"] == "RESIDENTIAL"
    assert result["reading_value_liters"] == 100.0
    assert result["reading_date"] is not None


def test_unknown_meter_is_flagged_not_dropped(spark):
    readings = _readings_df(spark, [_base_row(meter_id="MTR-999")])
    result = enrich_meter_readings(
        readings, _dim_meter_df(spark), _dim_customer_df(spark), _dim_dma_df(spark)
    ).first()

    assert result["is_known_meter"] is False
    assert result["meter_status"] == "UNKNOWN"
    assert result["account_type"] == "UNKNOWN"


def test_reading_value_standardized_to_liters(spark):
    readings = _readings_df(spark, [_base_row(unit="GALLONS", reading_value=1.0)])
    result = enrich_meter_readings(
        readings, _dim_meter_df(spark), _dim_customer_df(spark), _dim_dma_df(spark)
    ).first()

    assert abs(result["reading_value_liters"] - 3.785411784) < 1e-9


def test_unknown_dma_does_not_drop_the_row(spark):
    readings = _readings_df(spark, [_base_row(dma_id="DMA-999")])
    result = enrich_meter_readings(
        readings, _dim_meter_df(spark), _dim_customer_df(spark), _dim_dma_df(spark)
    ).first()

    assert result is not None
    assert result["dma_name"] == "UNKNOWN"
