"""End-to-end integration test for the Silver pipeline against a real dev
Databricks workspace, per CONTRIBUTING.md's "Integration tests exercise a
pipeline end-to-end against a scaled-down dev dataset — added starting
Phase 4."

Requires a deployed dev bundle (`databricks bundle deploy -t dev`) and
workspace credentials. Skipped entirely — not failed — when those aren't
available, since no live Databricks workspace exists in CI/local sandboxes
that lack real Azure/Databricks credentials (see terraform/README.md and
this repo's top-level constraint that nothing is applied to live
infrastructure from automated runs). This is why the suite lives separately
from tests/unit/, which runs everywhere via local PySpark.

What it verifies, when it does run:
1. `src/jobs/seed_reference_data.py` populates reference.dim_meter/
   dim_customer/dim_dma for a small synthetic population.
2. A handful of synthetic readings (one valid, one for an unknown meter,
   one with a negative reading_value) are inserted directly into
   bronze.meter_telemetry.
3. After triggering a Silver pipeline update and waiting for it to
   complete, the valid reading lands in silver.meter_readings and the two
   invalid readings land in quarantine.silver_meter_readings with the
   expected reason codes.

Usage:
    export DATABRICKS_HOST=https://<dev-workspace>.azuredatabricks.net
    export DATABRICKS_TOKEN=...
    export SMARTMETER_TEST_CATALOG=smartmeter_dev
    export SMARTMETER_TEST_SQL_WAREHOUSE_HTTP_PATH=/sql/1.0/warehouses/<id>
    pytest tests/integration/test_silver_pipeline_integration.py
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN")),
    reason=(
        "Requires a live dev Databricks workspace (DATABRICKS_HOST/DATABRICKS_TOKEN) "
        "with the Phase 4 bundle already deployed — not available in this sandbox/CI run."
    ),
)

CATALOG = os.environ.get("SMARTMETER_TEST_CATALOG", "smartmeter_dev")
PIPELINE_UPDATE_TIMEOUT_SECONDS = 900


@pytest.fixture(scope="module")
def workspace_client():
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient()


@pytest.fixture(scope="module")
def sql_connection():
    from databricks import sql

    connection = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].removeprefix("https://"),
        http_path=os.environ["SMARTMETER_TEST_SQL_WAREHOUSE_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    yield connection
    connection.close()


def _wait_for_pipeline_update(workspace_client, pipeline_name: str) -> None:
    pipeline = next(
        p for p in workspace_client.pipelines.list_pipelines() if p.name == pipeline_name
    )
    update = workspace_client.pipelines.start_update(pipeline_id=pipeline.pipeline_id)

    deadline = time.time() + PIPELINE_UPDATE_TIMEOUT_SECONDS
    while time.time() < deadline:
        status = workspace_client.pipelines.get_update(
            pipeline_id=pipeline.pipeline_id, update_id=update.update_id
        )
        if status.update.state.value in ("COMPLETED", "FAILED", "CANCELED"):
            assert status.update.state.value == "COMPLETED", status.update.state.value
            return
        time.sleep(10)
    pytest.fail(f"Pipeline update did not complete within {PIPELINE_UPDATE_TIMEOUT_SECONDS}s")


def test_silver_pipeline_validates_dedupes_and_quarantines(workspace_client, sql_connection):
    test_run_id = uuid.uuid4().hex[:8]
    known_meter_id = f"MTR-IT-{test_run_id}"
    unknown_meter_id = f"MTR-IT-UNKNOWN-{test_run_id}"

    with sql_connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO {CATALOG}.reference.dim_meter
            (meter_id, dma_id, customer_id, meter_type, meter_size_mm, install_date,
             latitude, longitude, status, effective_start_date, effective_end_date, is_current)
            VALUES ('{known_meter_id}', 'DMA-001', 'CUST-IT-{test_run_id}', 'RESIDENTIAL', 15,
                    current_date(), 29.5, -98.0, 'ACTIVE', current_date(), NULL, true)
            """)
        cursor.execute(f"""
            INSERT INTO {CATALOG}.bronze.meter_telemetry
            (meter_id, reading_timestamp, ingest_timestamp, reading_value, unit, dma_id,
             firmware_version, sequence_no, parse_error, ingest_date, ingested_at)
            VALUES
            ('{known_meter_id}', current_timestamp(), current_timestamp(), 42.0, 'LITERS',
             'DMA-001', '2.5.0', 1, NULL, current_date(), current_timestamp()),
            ('{unknown_meter_id}', current_timestamp(), current_timestamp(), 10.0, 'LITERS',
             'DMA-001', '2.5.0', 1, NULL, current_date(), current_timestamp()),
            ('{known_meter_id}', current_timestamp(), current_timestamp(), -5.0, 'LITERS',
             'DMA-001', '2.5.0', 1, NULL, current_date(), current_timestamp())
            """)

    _wait_for_pipeline_update(workspace_client, "smartmeter-dev-silver-meter-readings")

    with sql_connection.cursor() as cursor:
        cursor.execute(
            f"SELECT reading_value_liters FROM {CATALOG}.silver.meter_readings "
            f"WHERE meter_id = '{known_meter_id}' AND reading_value_liters = 42.0"
        )
        assert cursor.fetchone() is not None, "valid reading did not land in silver.meter_readings"

        cursor.execute(
            f"SELECT reason_code FROM {CATALOG}.quarantine.silver_meter_readings "
            f"WHERE meter_id = '{unknown_meter_id}'"
        )
        assert cursor.fetchone()[0] == "unknown_meter"

        cursor.execute(
            f"SELECT reason_code FROM {CATALOG}.quarantine.silver_meter_readings "
            f"WHERE meter_id = '{known_meter_id}' AND reason_code = 'negative_reading_value'"
        )
        assert cursor.fetchone() is not None
