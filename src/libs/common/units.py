"""Volumetric unit standardization for Silver's enrichment step.

Bronze preserves `reading_value`/`unit` exactly as the meter reported them
(GALLONS and CUBIC_METERS firmwares exist in the field alongside LITERS —
see schemas/avro/meter_telemetry.avsc). Silver standardizes every reading to
liters so Gold aggregates (Phase 5) never need to know a meter's reporting
unit. See docs/architecture/ARCHITECTURE.md#3-bronze--silver
("Standardization & enrichment").
"""

from __future__ import annotations

from pyspark.sql import Column
from pyspark.sql import functions as F

LITERS_PER_GALLON = 3.785411784
LITERS_PER_CUBIC_METER = 1000.0

_CONVERSION_FACTORS_TO_LITERS = {
    "LITERS": 1.0,
    "GALLONS": LITERS_PER_GALLON,
    "CUBIC_METERS": LITERS_PER_CUBIC_METER,
}


def to_liters(value_col: Column, unit_col: Column) -> Column:
    """Converts a reading value to liters given its reported unit.

    An unrecognized `unit` (a firmware value predating a schema update)
    yields NULL rather than silently guessing a conversion factor — the row
    is then caught by the `missing_reading_value` expectation and
    quarantined instead of landing in Silver with a wrong volume.
    """
    factor = F.lit(None).cast("double")
    for unit, conversion in _CONVERSION_FACTORS_TO_LITERS.items():
        factor = F.when(unit_col == unit, F.lit(conversion)).otherwise(factor)
    return value_col * factor
