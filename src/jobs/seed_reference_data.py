"""Seeds reference.dim_meter, reference.dim_customer, and reference.dim_dma
with a representative synthetic population, using the same generator that
backs local Bronze testing (tools/mock_data_generator/generator.py) — so the
dev/staging meter population Silver enriches against matches the population
the Event Hub simulator actually publishes telemetry for.

A plain batch Databricks Job task (src/jobs/, not a Lakeflow pipeline): this
is a one-off/idempotent seeding operation, not a continuous or incrementally
scheduled transformation, so it doesn't fit Lakeflow's declarative model —
see ADR-0003's consequence that genuinely imperative/one-shot logic lives
outside Lakeflow. Re-running it is safe and additive-only: existing keys are
left untouched and only new keys are inserted (see
`_insert_missing_current_versions`) — it is meant to be run manually or from
a low-frequency schedule, not on every pipeline update.

Usage (as a Databricks Job task — see bundles/seed_reference_data_job.yml):
    python -m src.jobs.seed_reference_data --meters 10000

Requires a SparkSession with Unity Catalog access to `<catalog>.reference`.
"""

from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from src.libs.monitoring.logger import get_logger
from tools.mock_data_generator.generator import (
    generate_customer_master,
    generate_dma_reference,
    generate_meter_master,
)

DIM_METER_SCHEMA = StructType(
    [
        StructField("meter_id", StringType(), nullable=False),
        StructField("dma_id", StringType(), nullable=False),
        StructField("customer_id", StringType(), nullable=False),
        StructField("meter_type", StringType(), nullable=False),
        StructField("meter_size_mm", IntegerType(), nullable=False),
        StructField("install_date", DateType(), nullable=False),
        StructField("latitude", DoubleType(), nullable=False),
        StructField("longitude", DoubleType(), nullable=False),
        StructField("status", StringType(), nullable=False),
    ]
)

DIM_CUSTOMER_SCHEMA = StructType(
    [
        StructField("customer_id", StringType(), nullable=False),
        StructField("account_name", StringType(), nullable=False),
        StructField("account_type", StringType(), nullable=False),
        StructField("service_address", StringType(), nullable=False),
        StructField("connection_date", DateType(), nullable=False),
        StructField("billing_cycle_day", IntegerType(), nullable=False),
    ]
)

DIM_DMA_SCHEMA = StructType(
    [
        StructField("dma_id", StringType(), nullable=False),
        StructField("dma_name", StringType(), nullable=False),
        StructField("zone", StringType(), nullable=False),
        StructField("supply_source", StringType(), nullable=False),
        StructField("population_served", IntegerType(), nullable=False),
        StructField("target_nrw_pct", DoubleType(), nullable=False),
    ]
)


def _stamp_scd2_current_version(df: DataFrame) -> DataFrame:
    """Adds the SCD2 bookkeeping columns for a freshly generated "current"
    version of a dimension row. `effective_start_date` uses today's date
    rather than a synthetic install/connection date, since this column
    tracks when *this dimension row version* became effective, not the
    real-world event the row describes.
    """
    return (
        df.withColumn("effective_start_date", F.current_date())
        .withColumn("effective_end_date", F.lit(None).cast("date"))
        .withColumn("is_current", F.lit(True))
    )


def _insert_missing_current_versions(
    spark: SparkSession, source: DataFrame, target_fqn: str, key_col: str
) -> None:
    """Inserts a new "current" SCD2 row for every key in `source` that does
    not already have a current row in `target_fqn` — idempotent re-runs
    (e.g. widening `--meters`) only add the newly generated keys.

    Deliberately insert-only, not full SCD2 change detection (closing out a
    current row whose attributes changed): this is a one-off/representative
    *seed*, not an ongoing change feed — real attribute changes for an
    existing meter/customer (a DMA reassignment, an address update) are
    expected to arrive as actual SCD2 update events from a source system in
    a real deployment, not be synthesized by re-running this generator.
    """
    if not spark.catalog.tableExists(target_fqn):
        source.write.format("delta").saveAsTable(target_fqn)
        return

    source.createOrReplaceTempView("_seed_source")

    new_rows = spark.sql(f"""
        SELECT s.*
        FROM _seed_source s
        LEFT JOIN {target_fqn} t
          ON s.{key_col} = t.{key_col} AND t.is_current = true
        WHERE t.{key_col} IS NULL
        """)
    new_rows.write.format("delta").mode("append").saveAsTable(target_fqn)


def seed_reference_data(spark: SparkSession, catalog: str, meter_count: int, seed: int) -> None:
    logger = get_logger(pipeline="seed_reference_data", layer="reference", run_id=str(seed))

    meters = generate_meter_master(meter_count, seed=seed)
    customers = generate_customer_master(meters, seed=seed)
    dmas = generate_dma_reference(seed=seed)

    dim_meter = _stamp_scd2_current_version(
        spark.createDataFrame(
            [
                (
                    m.meter_id,
                    m.dma_id,
                    m.customer_id,
                    m.meter_type,
                    m.meter_size_mm,
                    m.install_date,
                    m.latitude,
                    m.longitude,
                    "ACTIVE",
                )
                for m in meters
            ],
            schema=DIM_METER_SCHEMA,
        )
    )
    dim_customer = _stamp_scd2_current_version(
        spark.createDataFrame(
            [
                (
                    c.customer_id,
                    c.account_name,
                    c.account_type,
                    c.service_address,
                    c.connection_date,
                    c.billing_cycle_day,
                )
                for c in customers
            ],
            schema=DIM_CUSTOMER_SCHEMA,
        )
    )
    dim_dma = spark.createDataFrame(
        [
            (d.dma_id, d.dma_name, d.zone, d.supply_source, d.population_served, d.target_nrw_pct)
            for d in dmas
        ],
        schema=DIM_DMA_SCHEMA,
    )

    _insert_missing_current_versions(
        spark, dim_meter, f"{catalog}.reference.dim_meter", key_col="meter_id"
    )
    logger.info(f"Seeded {dim_meter.count()} meter rows.")

    _insert_missing_current_versions(
        spark, dim_customer, f"{catalog}.reference.dim_customer", key_col="customer_id"
    )
    logger.info(f"Seeded {dim_customer.count()} customer rows.")

    # dim_dma is Type 1 (overwrite in place) — see sql/ddl/reference_dim_dma.sql.
    dim_dma.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.reference.dim_dma")
    logger.info(f"Seeded {dim_dma.count()} DMA rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    parser.add_argument("--meters", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    seed_reference_data(spark, catalog=args.catalog, meter_count=args.meters, seed=args.seed)


if __name__ == "__main__":
    main()
