"""Shared pytest fixtures for tests that need a local Spark session.

Silver/Gold transformation logic in src/libs/ is plain PySpark DataFrame
code (no Lakeflow-specific decorators), so it's testable against a local
SparkSession without a Databricks workspace — only the pipeline wiring in
src/pipelines/ (which does use Databricks Runtime-provided `dp.table`,
`dp.apply_changes`, etc.) is exempted from local testing, per the F821
exemption in pyproject.toml.
"""

import pytest


@pytest.fixture(scope="session")
def spark():
    pytest.importorskip("pyspark", reason="pyspark not installed locally")
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("smart-metering-platform-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()
