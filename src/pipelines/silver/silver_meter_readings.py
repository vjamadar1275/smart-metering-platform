"""Silver layer: cleansed, deduplicated, enriched meter readings.

Lakeflow Declarative Pipeline (see bundles/silver_pipeline.yml for
deployment, docs/architecture/ARCHITECTURE.md#3-bronze--silver for the
design, ADR-0003 for Lakeflow Expectations, ADR-0004 for the Liquid
Clustering key used on `silver.meter_readings`).

Reads Bronze's raw meter telemetry and, in order:

1. Enriches against the meter/customer/DMA reference dimensions
   (`src/jobs/seed_reference_data.py` populates these) and standardizes
   `reading_value` to liters (`src/libs/common/enrichment.py`).
2. Validates the enriched rows against `src/libs/quality/expectations.py`'s
   rules. Rows failing any rule are quarantined into
   `quarantine.silver_meter_readings` with a reason code — never silently
   dropped.
3. Deduplicates the valid rows via a Delta MERGE (Lakeflow AUTO CDC) keyed
   on `(meter_id, reading_timestamp)`, since meters/gateways can redeliver
   the same reading on retry.

A 24-hour watermark on `reading_timestamp` bounds streaming state for step 3
while accommodating realistic field connectivity gaps. Readings arriving
after the watermark are still captured — not dropped — by the nightly batch
job `src/jobs/silver_late_arrival_reconciliation.py`, which is not part of
this continuous streaming pipeline (see that module's docstring for why).
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from src.libs.common.enrichment import REQUIRED_READING_COLUMNS, enrich_meter_readings
from src.libs.io.reference_data import read_current_scd2_dimension, read_dma_dimension
from src.libs.quality.expectations import (
    METER_READING_EXPECTATIONS,
    all_rules_expression,
    first_failure_reason_code,
)

# Populated from the Lakeflow pipeline's `configuration` block (see
# bundles/silver_pipeline.yml) — never hardcoded here, per CONTRIBUTING.md's
# "no hardcoded environment values" rule.
_conf = spark.conf
CATALOG = _conf.get("smartmeter.catalog_name")
WATERMARK_DURATION = _conf.get("smartmeter.silver.watermark_duration", "24 hours")

BRONZE_TABLE = f"{CATALOG}.bronze.meter_telemetry"
DIM_METER_TABLE = f"{CATALOG}.reference.dim_meter"
DIM_CUSTOMER_TABLE = f"{CATALOG}.reference.dim_customer"
DIM_DMA_TABLE = f"{CATALOG}.reference.dim_dma"


def _read_bronze_stream():
    return (
        spark.readStream.table(BRONZE_TABLE)
        # Bronze already tags Avro parse failures with `parse_error` and
        # keeps them (never drops them) for replay — those rows have no
        # parsed business fields to validate/enrich, so re-surfacing them
        # in Silver's quarantine would just duplicate what Bronze already
        # records, not add information.
        .where("parse_error IS NULL")
        .withWatermark("reading_timestamp", WATERMARK_DURATION)
        .select(*REQUIRED_READING_COLUMNS)
    )


@dp.view
def silver_enriched_readings():
    """Bronze telemetry joined against current reference dimensions and
    standardized to liters — the shared input both the clean-row flow and
    the quarantine flow below read from, so enrichment runs exactly once
    per row rather than being duplicated across the two.
    """
    bronze = _read_bronze_stream()
    dim_meter = read_current_scd2_dimension(spark, DIM_METER_TABLE)
    dim_customer = read_current_scd2_dimension(spark, DIM_CUSTOMER_TABLE)
    dim_dma = read_dma_dimension(spark, DIM_DMA_TABLE)
    return enrich_meter_readings(bronze, dim_meter, dim_customer, dim_dma)


@dp.table(
    name="silver_meter_readings_valid",
    comment=(
        "Intermediate staging table: enriched readings that pass every "
        "quality rule. Feeds the MERGE-based dedup flow into "
        "silver.meter_readings below — not intended to be queried "
        "directly, query silver.meter_readings instead."
    ),
    temporary=True,
)
@dp.expect_all_or_drop(METER_READING_EXPECTATIONS)
def silver_meter_readings_valid():
    return dp.read_stream("silver_enriched_readings")


dp.create_streaming_table(
    name="silver.meter_readings",
    comment=(
        "Validated, deduplicated, enriched meter readings — the single "
        "source of truth Gold (Phase 5) builds on. See "
        "docs/architecture/ARCHITECTURE.md#3-bronze--silver."
    ),
    table_properties={
        "delta.enableChangeDataFeed": "true",
        "quality": "silver",
    },
    # Liquid Clustering, not static partitioning — ADR-0004. `meter_id`
    # supports the "all readings for meter X" access pattern, `reading_date`
    # supports time-range scans; neither needs low cardinality the way a
    # Hive partition column would.
    cluster_by=["meter_id", "reading_date"],
)

dp.create_auto_cdc_flow(
    target="silver.meter_readings",
    source="silver_meter_readings_valid",
    keys=["meter_id", "reading_timestamp"],
    # Redelivered retries of the same reading are expected to be identical;
    # sequencing by ingest_timestamp means if they ever do differ (e.g. a
    # gateway resending with corrected metadata), the most recently
    # ingested version wins.
    sequence_by="ingest_timestamp",
    stored_as_scd_type=1,
)


@dp.table(
    name="quarantine.silver_meter_readings",
    comment=(
        "Enriched readings that failed at least one Silver validation "
        "rule, with the first-failing rule's reason code. Not dropped — "
        "see docs/architecture/ARCHITECTURE.md#3-bronze--silver "
        "('Validation'). Reprocessed once the underlying cause (e.g. a "
        "missing reference.dim_meter row) is fixed."
    ),
    table_properties={
        "delta.enableChangeDataFeed": "true",
        "quality": "quarantine",
    },
)
def quarantine_silver_meter_readings():
    enriched = dp.read_stream("silver_enriched_readings")
    return (
        enriched.where(~all_rules_expression())
        .withColumn("reason_code", first_failure_reason_code())
        .withColumn("quarantined_at", F.current_timestamp())
    )
