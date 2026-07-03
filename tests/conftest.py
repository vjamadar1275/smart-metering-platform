"""Shared pytest fixtures.

`spark` is the first fixture in this repo backing tests that exercise real
PySpark DataFrame transforms (src/libs/, starting Phase 4) rather than pure
Python — see requirements-dev.txt for the pinned local pyspark/delta-spark
versions. Delta extensions are enabled by default since Silver/Gold tables
are all Delta (Bronze too) — tests that write/read Delta tables (e.g. the
reference-data seed job) need no extra fixture.
"""

from __future__ import annotations

import pytest
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    builder = (
        SparkSession.builder.master("local[2]")
        .appName("smart-metering-platform-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    yield session
    session.stop()
