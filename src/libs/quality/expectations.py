"""Silver quality rules: hard (quarantine-triggering) and soft (metric-only)
expectations, plus the quarantine-reason computation shared by the Silver
pipeline (src/pipelines/silver/silver_meter_readings.py) and its unit tests.

Lakeflow Expectations (`dp.expect_all`, a Databricks Runtime-provided
decorator — not present in the OSS pyspark.pipelines stub used for local
linting, same as `spark`/`dbutils`; see the F821 exemption in
pyproject.toml) give per-rule pass/fail *metrics*, but they don't attach a
reason code to the row that failed, and `expect_all_or_drop` would drop it
outright — unacceptable per docs/architecture/ARCHITECTURE.md#3-bronze--
silver ("Failing rows are quarantined ... with a reason code, not dropped
silently"). So the hard rules below are evaluated as plain columns,
producing a `quarantine_reasons: array<string>` that the pipeline uses to
split rows between silver.meter_readings and
quarantine.silver_meter_readings_quarantine.
"""

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from src.libs.common.units import VALID_UNITS

MAX_PLAUSIBLE_CUMULATIVE_LITERS = 1_000_000_000.0
"""Sanity ceiling on a single cumulative reading, in liters. Generous enough
to never reject a genuine meter's lifetime totalizer value; exists only to
catch corrupt/sentinel sensor values (e.g. a stuck register reporting
2**32-1)."""

MAX_CLOCK_SKEW_HOURS = 1
"""How far into the future (relative to Silver processing time) a device
reading_timestamp may plausibly be, allowing for uncorrected device clock
drift without accepting obviously-wrong future dates."""

# Soft expectations: tracked as Lakeflow metrics via `dp.expect_all` in the
# pipeline, but never quarantine or drop a row — a meter with a flat/dead
# battery still reports real volumetric data that's fully usable downstream.
SOFT_EXPECTATIONS = {
    "battery_pct_in_range": "battery_pct IS NULL OR battery_pct BETWEEN 0 AND 100",
    "signal_quality_in_range": "signal_quality IS NULL OR signal_quality BETWEEN 0 AND 100",
}


def _reason(is_valid: Column, code: str) -> Column:
    """`is_valid` is the condition for the row being acceptable; returns
    `code` when it evaluates to false (violated) or NULL (indeterminate —
    treated as a violation, since an expectation that can't be evaluated
    shouldn't pass by default), and NULL when satisfied.
    `array_compact` (in the caller) drops the resulting NULLs."""
    return F.when(is_valid, F.lit(None).cast("string")).otherwise(F.lit(code))


def with_quarantine_reasons(
    enriched: DataFrame,
    *,
    max_plausible_liters: float = MAX_PLAUSIBLE_CUMULATIVE_LITERS,
    max_clock_skew_hours: int = MAX_CLOCK_SKEW_HOURS,
) -> DataFrame:
    """Adds `quarantine_reasons` (array<string>, empty when valid) and
    `is_valid` (bool) to a Bronze-sourced DataFrame already left-joined
    against current reference dimension rows.

    Expects these columns to already be present (produced by the Silver
    pipeline's enrichment join — see silver_meter_readings.py):
      meter_id, reading_timestamp, reading_value, unit, parse_error,
      ref_meter_status, ref_meter_expected_unit, ref_meter_install_date,
      ref_dma_id (all `ref_*` columns NULL when meter_id/dma_id has no
      matching current reference row).
    """
    reasons = F.array_compact(
        F.array(
            _reason(F.col("parse_error").isNull(), "bronze_parse_error"),
            _reason(F.col("meter_id").isNotNull(), "missing_meter_id"),
            _reason(F.col("reading_timestamp").isNotNull(), "missing_reading_timestamp"),
            _reason(F.col("reading_value").isNotNull(), "missing_reading_value"),
            _reason(
                F.col("unit").isNotNull() & F.col("unit").isin(*VALID_UNITS),
                "invalid_unit",
            ),
            _reason(
                F.col("reading_value").isNull() | (F.col("reading_value") >= 0),
                "negative_reading",
            ),
            _reason(
                F.col("reading_value").isNull() | (F.col("reading_value") <= max_plausible_liters),
                "implausible_reading_magnitude",
            ),
            _reason(
                F.col("reading_timestamp").isNull()
                | (
                    F.col("reading_timestamp")
                    <= F.current_timestamp() + F.make_interval(hours=F.lit(max_clock_skew_hours))
                ),
                "reading_timestamp_in_future",
            ),
            _reason(F.col("ref_meter_status").isNotNull(), "unknown_meter_id"),
            _reason(
                F.col("ref_meter_status").isNull() | (F.col("ref_meter_status") == "ACTIVE"),
                "meter_not_active",
            ),
            _reason(
                F.col("ref_meter_install_date").isNull()
                | F.col("reading_timestamp").isNull()
                | (F.to_date(F.col("reading_timestamp")) >= F.col("ref_meter_install_date")),
                "reading_before_install",
            ),
            _reason(
                F.col("ref_meter_expected_unit").isNull()
                | F.col("unit").isNull()
                | (F.col("unit") == F.col("ref_meter_expected_unit")),
                "unit_mismatch",
            ),
            _reason(F.col("ref_dma_id").isNotNull(), "unknown_dma_id"),
        )
    )
    return enriched.withColumn("quarantine_reasons", reasons).withColumn(
        "is_valid", F.size("quarantine_reasons") == 0
    )
