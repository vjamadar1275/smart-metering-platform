"""Silver enrichment: joins validated meter telemetry against the
meter/customer/DMA reference dimensions and standardizes volumetric units.

Per docs/architecture/ARCHITECTURE.md#3-bronze--silver ("Standardization &
enrichment"). A pure DataFrame -> DataFrame transform, identically reusable
by the streaming Silver pipeline
(src/pipelines/silver/silver_meter_readings.py) and the nightly late-arrival
batch reconciliation job (src/jobs/silver_late_arrival_reconciliation.py) —
one enrichment implementation, not two that can drift.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.libs.common.units import to_liters

# Columns enrich_meter_readings() requires on its `readings` input, beyond
# the raw telemetry fields — documents the contract without needing a full
# schema object for what is otherwise a plain DataFrame transform.
REQUIRED_READING_COLUMNS = (
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
)


def enrich_meter_readings(
    readings: DataFrame,
    dim_meter: DataFrame,
    dim_customer: DataFrame,
    dim_dma: DataFrame,
) -> DataFrame:
    """Left-joins `readings` (Bronze telemetry columns, see
    REQUIRED_READING_COLUMNS) against the current meter/customer/DMA
    dimension rows and standardizes `reading_value` to liters.

    Left joins (not inner) are deliberate: a reading for a meter not yet in
    reference.dim_meter must still be quarantined *with a reason code*
    (`unknown_meter`, see src/libs/quality/expectations.py) rather than
    silently vanish, which an inner join would do.

    `is_known_meter` is true only if the left join to dim_meter matched —
    expectations.py's `unknown_meter` rule reads this column, so enrichment
    must run before expectations are evaluated.
    """
    joined = (
        readings.join(
            dim_meter.select(
                "meter_id",
                "customer_id",
                "meter_type",
                "meter_size_mm",
                F.col("status").alias("meter_status"),
            ),
            on="meter_id",
            how="left",
        ).join(
            dim_customer.select(
                "customer_id",
                "account_name",
                "account_type",
                "service_address",
            ),
            on="customer_id",
            how="left",
        )
        # Joined on the reading's own reported dma_id (not dim_meter's
        # current DMA assignment) so a meter reassigned to a new DMA after
        # this reading was taken still enriches with the DMA that was
        # actually in effect at reading time.
        .join(
            dim_dma.select(
                "dma_id",
                "dma_name",
                F.col("zone").alias("dma_zone"),
            ),
            on="dma_id",
            how="left",
        )
    )

    return joined.select(
        joined["meter_id"],
        joined["reading_timestamp"],
        joined["ingest_timestamp"],
        to_liters(joined["reading_value"], joined["unit"]).alias("reading_value_liters"),
        joined["flow_rate"],
        joined["battery_pct"],
        joined["signal_quality"],
        joined["dma_id"],
        F.coalesce(joined["dma_name"], F.lit("UNKNOWN")).alias("dma_name"),
        F.coalesce(joined["dma_zone"], F.lit("UNKNOWN")).alias("dma_zone"),
        joined["firmware_version"],
        joined["sequence_no"],
        joined["customer_id"],
        joined["account_name"],
        F.coalesce(joined["account_type"], F.lit("UNKNOWN")).alias("account_type"),
        joined["service_address"],
        joined["meter_type"],
        joined["meter_size_mm"],
        F.coalesce(joined["meter_status"], F.lit("UNKNOWN")).alias("meter_status"),
        joined["meter_type"].isNotNull().alias("is_known_meter"),
        F.to_date(joined["reading_timestamp"]).alias("reading_date"),
    )
