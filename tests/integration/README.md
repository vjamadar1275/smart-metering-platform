# Integration Tests

Exercise a deployed pipeline end-to-end against a real dev Databricks workspace, per [CONTRIBUTING.md](../../CONTRIBUTING.md)'s testing expectations. Unlike `tests/unit/` (pure PySpark, runs anywhere), these require:

- A dev bundle already deployed (`databricks bundle deploy -t dev`, from a machine/CI runner with real Azure/Databricks credentials — never run automatically in this repository's local/sandboxed development flow, see the top-level [README](../../README.md)).
- `DATABRICKS_HOST` / `DATABRICKS_TOKEN` environment variables for the dev workspace.
- A running SQL Warehouse (`SMARTMETER_TEST_SQL_WAREHOUSE_HTTP_PATH`) to query results.

Each test module is skipped (not failed) when these aren't present, so `pytest tests/` is always safe to run locally or in a CI job with no live workspace access — see each module's docstring for its exact `export`/usage instructions.

| Module | Verifies |
|---|---|
| [test_silver_pipeline_integration.py](test_silver_pipeline_integration.py) | Bronze → Silver end-to-end: valid rows land in `silver.meter_readings`, invalid rows land in `quarantine.silver_meter_readings` with the correct `reason_code`. |
