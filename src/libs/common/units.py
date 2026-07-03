"""Unit conversion helpers shared by Silver/Gold transformations.

Smart meters report cumulative volume in whichever unit their firmware is
configured for (see schemas/avro/meter_telemetry.avsc's `unit` field).
Silver standardizes every reading to liters (docs/architecture/ARCHITECTURE.md
#3-bronze--silver, "unit normalization: all volumes to liters") so Gold
aggregations never need to carry a unit column or branch on it.
"""

from pyspark.sql import Column
from pyspark.sql import functions as F

LITERS_PER_GALLON = 3.785411784
LITERS_PER_CUBIC_METER = 1000.0

VALID_UNITS = ("LITERS", "GALLONS", "CUBIC_METERS")

_LITERS_PER_UNIT = {
    "LITERS": 1.0,
    "GALLONS": LITERS_PER_GALLON,
    "CUBIC_METERS": LITERS_PER_CUBIC_METER,
}


def to_liters(value_col: Column, unit_col: Column) -> Column:
    """Converts a reading value to liters given its reported unit.

    Returns NULL for a unit outside `VALID_UNITS` rather than raising, so an
    unrecognized unit surfaces as a Silver quality-expectation failure
    (reason code `invalid_unit`, see src/libs/quality/expectations.py)
    instead of crashing the pipeline.
    """
    conversion = F.create_map([F.lit(x) for pair in _LITERS_PER_UNIT.items() for x in pair])
    return value_col * conversion[unit_col]
