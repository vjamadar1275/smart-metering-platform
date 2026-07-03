"""Reusable Lakeflow Expectations for Silver-layer data quality.

Centralizes the validation rules Silver applies to meter telemetry so the
same rule set drives both the streaming pipeline
(src/pipelines/silver/silver_meter_readings.py) and the nightly late-arrival
batch reconciliation job (src/jobs/silver_late_arrival_reconciliation.py) —
one set of business rules, not two copies that can silently drift apart.

Rules are expressed as SQL boolean-expression strings (not Column objects)
because that is the shape Lakeflow's `@dp.expect_all`/`expect_all_or_drop`
decorators take directly. `all_rules_expression` and
`first_failure_reason_code` build DataFrame-API Column objects from the same
strings via `F.expr`, so the manual quarantine-routing logic can never
diverge from what the decorator enforces.

See docs/architecture/ARCHITECTURE.md#3-bronze--silver ("Validation") and
ADR-0003 (Lakeflow Expectations) for the design this implements.
"""

from __future__ import annotations

from pyspark.sql import Column
from pyspark.sql import functions as F

# A cumulative totalizer reading above this is treated as sensor/parsing
# corruption rather than real consumption (no realistic residential/
# commercial/industrial connection reads this high). This is a stateless
# sanity ceiling, not the full "plausible delta from the previous reading"
# check described in ARCHITECTURE.md — that check requires comparing against
# a meter's prior value, which is inherently stateful and is therefore
# performed in the nightly batch reconciliation job (window/self-join
# support that Structured Streaming's per-row expectations do not have),
# not here.
MAX_PLAUSIBLE_READING_VALUE_LITERS = 10_000_000

# Applied to every row read from bronze.meter_telemetry, in order, after the
# meter/customer/DMA enrichment join (so `is_known_meter` is already
# populated — see src/libs/common/enrichment.py). reason_code -> SQL
# condition that is TRUE when the row PASSES this rule.
METER_READING_EXPECTATIONS: dict[str, str] = {
    "missing_meter_id": "meter_id IS NOT NULL",
    "missing_reading_timestamp": "reading_timestamp IS NOT NULL",
    "missing_dma_id": "dma_id IS NOT NULL",
    "negative_reading_value": "reading_value IS NOT NULL AND reading_value >= 0",
    "reading_value_out_of_range": (
        f"reading_value IS NULL OR reading_value < {MAX_PLAUSIBLE_READING_VALUE_LITERS}"
    ),
    "unknown_meter": "is_known_meter = true",
}


def all_rules_expression(rules: dict[str, str] = METER_READING_EXPECTATIONS) -> Column:
    """ANDs every rule together — TRUE only if a row passes every check.

    Used to filter the quarantine table down to rows that fail at least one
    rule (the complement of what `@dp.expect_all_or_drop(rules)` keeps).
    """
    condition = F.lit(True)
    for condition_sql in rules.values():
        condition = condition & F.expr(condition_sql)
    return condition


def first_failure_reason_code(rules: dict[str, str] = METER_READING_EXPECTATIONS) -> Column:
    """Returns the reason_code of the first failing rule (in `rules`
    iteration order), or NULL if the row passes every rule. Populates
    quarantine.silver_meter_readings.reason_code, mirroring Bronze's
    `parse_error` column pattern.
    """
    expr = F.lit(None).cast("string")
    for reason_code, condition_sql in reversed(list(rules.items())):
        expr = F.when(~F.expr(condition_sql), F.lit(reason_code)).otherwise(expr)
    return expr
