"""Reads Unity Catalog reference (dimension) tables for Silver enrichment.

Both the streaming Silver pipeline
(src/pipelines/silver/silver_meter_readings.py) and the nightly late-arrival
reconciliation job (src/jobs/silver_late_arrival_reconciliation.py) need the
*current* version of each SCD Type 2 dimension table, broadcast-joined since
dimension tables are small (tens of thousands of rows) relative to the
telemetry fact stream.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def read_current_scd2_dimension(spark: SparkSession, table_fqn: str) -> DataFrame:
    """Reads the current (`is_current = true`) version of an SCD Type 2
    Unity Catalog dimension table (reference.dim_meter, reference.dim_customer),
    broadcast-hinted for the small-dimension/large-fact join pattern.
    """
    return F.broadcast(spark.read.table(table_fqn).where("is_current = true"))


def read_dma_dimension(spark: SparkSession, table_fqn: str) -> DataFrame:
    """reference.dim_dma is Type 1 (overwrite in place, no SCD columns) —
    see sql/ddl/reference_dim_dma.sql — so no `is_current` filter applies.
    """
    return F.broadcast(spark.read.table(table_fqn))
