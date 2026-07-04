# Troubleshooting Guide

Common failure modes across the pipeline and their resolutions.

## Bronze

**Symptom: `parse_error` populated on a growing fraction of rows.**
Cause: a firmware update publishing a schema Bronze's static `schemas/avro/meter_telemetry.avsc` doesn't recognize (ADR-0009's accepted risk — the schema file and the Event Hubs Schema Registry group can drift). Fix: update `schemas/avro/meter_telemetry.avsc` to match the new firmware's schema (additive/optional fields only, per Bronze's permissive `mergeSchema` design) and redeploy the Bronze pipeline. Already-landed rows with `parse_error` are not automatically reprocessed — reprocess Bronze if the volume affected warrants it (the raw Avro bytes are preserved in `raw_payload` specifically for this).

**Symptom: Bronze streaming lag growing, no errors.**
See Performance Guide's streaming-lag playbook.

## Silver

**Symptom: elevated `quarantine.silver_meter_readings` volume for `reason_code = 'unknown_meter'`.**
Cause: readings for meters not yet present in `reference.dim_meter` — usually a new meter installed in the field before `seed_reference_data.py` (or, in production, a real CRM/GIS meter-provisioning integration — see that job's docstring on this being an open item for prod) has registered it. Fix: backfill the missing meter into `reference.dim_meter`, then either wait for the next `silver_late_arrival_reconciliation` run or manually reprocess the affected Bronze rows.

**Symptom: elevated `quarantine.silver_meter_readings` volume for `reason_code = 'negative_reading_value'` or `'reading_value_out_of_range'`.**
Cause: usually a genuine device fault (a meter reporting corrupted values) rather than a pipeline bug — check whether it's concentrated on one `firmware_version` or one meter, which would point at a device-side issue, versus spread evenly, which would point at an enrichment/unit-conversion bug (`src/libs/common/units.py`).

**Symptom: a reading that should be in `silver.meter_readings` isn't there, more than 24 hours after `reading_timestamp`.**
Check `quarantine.silver_meter_readings` first (it may have failed validation, not just been late). If not there and not in Silver, check whether it falls outside `silver_late_arrival_reconciliation`'s lookback window (default 7 days, ADR-0010) — widen `--lookback-days` for a one-off manual run (see Operations Guide's Backfills section) rather than assuming it's lost; Bronze retains it permanently either way.

## Gold

**Symptom: `gold.dma_analytics.non_revenue_water_pct` looks implausible (very high/negative/zero for every DMA).**
Remember this is an **estimated proxy** derived from `reference.dim_dma.target_nrw_pct`, not measured supply data (ADR-0011) — a uniformly wrong NRW figure across every DMA usually means `reference.dim_dma.target_nrw_pct` itself is wrong or missing for the affected DMAs (check via `SELECT dma_id, target_nrw_pct FROM reference.dim_dma`), not a bug in the NRW formula itself.

**Symptom: `gold.daily_usage`/`gold.dma_analytics`/`gold.customer_analytics` look stale (yesterday's data missing).**
These are triggered/batch, not streaming (ADR-0011) — check `gold_daily_marts_trigger`'s job run history (`bundles/gold_batch_pipeline.yml`, 05:00 UTC schedule) before assuming a pipeline bug; a late Silver reconciliation run (03:00 UTC) finishing after 05:00 for that day would also delay that day's Gold marts by one cycle.

## ML

**Symptom: a training script (`src/ml/training/*.py`) fails with "Only N labeled rows available (need >= M)".**
Not a bug — each script's `MIN_TRAINING_ROWS` threshold exists because these models genuinely need that much history for their feature windows (trailing 7/14-day baselines, a 30-day forward label horizon) to produce meaningful data — see each training script's error message for exactly how much history it needs and why (e.g. predictive maintenance needs ~44 days: 14-day trend window + 30-day label horizon). Wait for more data to accumulate, or lower the threshold deliberately if you understand the trade-off (a smaller, noisier training set).

**Symptom: the NL agent (`src/ml/agent/nl_analytics_agent.py`) rejects a query you believe is safe.**
Check `validate_readonly_query`'s rejection reason — it's specific (parse failure, wrong statement type, multi-statement, or disallowed schema/table). If a schema-qualified table reference is being flagged incorrectly, this is exactly the class of bug ADR-0012 documents fixing once already (an alias being mistaken for a schema) — file it as a real bug against `sqlglot`-based table extraction, not something to route around by loosening the check.

## Terraform / Infrastructure

**Symptom: `terraform plan`/`apply` fails with a provider registry connection error.**
If running from a network with egress restrictions (as this repository's own sandboxed development environment has — see prior commit messages), `registry.terraform.io` may be blocked by policy. This is an environment/network constraint, not a code bug — `terraform fmt -check` and `terraform validate` (syntax-only, no provider download) still work and are what this repository's own commits have validated with; `plan`/`apply` need a network path to the provider registry.

**Symptom: `databricks bundle validate`/`deploy` fails to install the CLI.**
Same class of issue — GitHub release downloads may be blocked by network egress policy in a restricted environment. Use `databricks/setup-cli@main`'s GitHub Action in CI (which runs in GitHub's own unrestricted runners), or install the CLI on a machine with unrestricted network access.

## CI/CD

**Symptom: `terraform-plan.yml`/`bundle-deploy.yml`/`terraform-apply.yml` jobs are skipped, not failed.**
Expected until an admin configures that environment's secrets/repo variables (`ARM_CLIENT_ID` etc., `TERRAFORM_CREDENTIALS_CONFIGURED_<ENV>`, `DATABRICKS_BUNDLE_DEPLOY_ENABLED`) — see each workflow's own comments for exactly which gate it checks. A hard-failing CI job here would be permanently red for no actionable reason until real credentials exist, which is why these are designed to skip cleanly instead.
