# Operations Guide

Day-2 operations: restarting pipelines, backfills, scaling, and what's on-call actually looks at when paged.

## Pipeline restarts

| Pipeline | Restart command | What resumes |
|---|---|---|
| `bronze_meter_telemetry` | `databricks bundle run bronze_meter_telemetry -t <env>` | Structured Streaming checkpoint in ADLS — resumes from the last committed Event Hub offset, never re-reads or skips (see ARCHITECTURE.md's Bronze design). |
| `silver_meter_readings` | `databricks bundle run silver_meter_readings -t <env>` | Same checkpoint-based resume; the AUTO CDC flow re-derives state from `silver.meter_readings`'s existing rows. |
| `gold_hourly_consumption` | `databricks bundle run gold_hourly_consumption -t <env>` | Streaming aggregation checkpoint. |
| `gold_daily_marts` | `databricks bundle run gold_daily_marts -t <env>` | Triggered/batch — a restart just re-runs the full recompute (see `gold_daily_marts.py`'s docstring on why these are full recomputes, not incremental). |

A pipeline stopped for more than its watermark/lookback window (Silver: 24h watermark + `silver_late_arrival_reconciliation`'s 7-day lookback) does **not** lose data — Bronze retains everything, and reconciliation catches up automatically on its next scheduled run. Restarting sooner is about latency, not correctness.

## Backfills

- **Reference data** (`reference.dim_meter`/`dim_customer`/`dim_dma`): `databricks bundle run seed_reference_data -t <env> -- --meters <count>` — additive/idempotent (`src/jobs/seed_reference_data.py`'s `_insert_missing_current_versions`), safe to re-run with a larger `--meters` count.
- **Late-arriving Silver data beyond the default 7-day lookback**: run `src/jobs/silver_late_arrival_reconciliation.py` manually with a wider `--lookback-days`, e.g. `databricks bundle run silver_late_arrival_reconciliation -t <env> -- --lookback-days 30`. This is the manual escalation path ADR-0010 describes for arrivals later than the nightly job's default window.
- **Gold marts after a Silver logic fix**: `gold_daily_marts` is a full recompute on every triggered run (see Developer Guide), so simply re-running it picks up any Silver correction automatically — no separate Gold-specific backfill mechanism needed.
- **ML models after a feature-engineering fix**: `databricks bundle run ml_model_training -t <env>` re-trains and re-registers all four models against current Gold data.

## Scaling

- **Bronze/Silver/Gold-hourly** (continuous pipelines): Serverless autoscaling handles load automatically (ADR-0007) — no manual scaling action for normal load growth. If `maxOffsetsPerTrigger` (Bronze) or the equivalent backlog-catch-up behavior looks throttled, check `src/config/<env>/bronze_pipeline.json`'s `max_offsets_per_trigger` against current Event Hub throughput (`terraform output` on the `event_hub` module, or the Azure portal).
- **SQL Warehouses**: `terraform/modules/sql-warehouse/README.md`'s sizing table is a starting point, not final — resize `min_clusters`/`max_clusters`/`cluster_size` per warehouse based on `sql/observability/warehouse_query_performance.sql`'s p95 latency and queueing signals, then `terraform apply` (via the `terraform-apply.yml` GitHub Action, environment-gated).
- **Event Hub partitions/capacity units**: sized in `terraform/environments/<env>/main.tf`'s `event_hub` module call — increasing partition count is a breaking change to consumer parallelism assumptions (ADR-0001's partition-key-by-meter_id design) and should be planned, not done reactively under load.

## What on-call looks at

1. **Pipeline/job failure alert** (`terraform/modules/monitoring`'s `pipeline_failures` alert rule, or a pipeline's own `notifications:`/`email_notifications:` block in `bundles/*.yml`) — check the Lakeflow pipeline's event log / job run page first; most failures are either a transient cloud issue (retry) or a genuine upstream schema/data problem (see [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md)).
2. **Quarantine rate spike** (`gold.operational_dashboard.quarantine_rate_pct`, or query `quarantine.silver_meter_readings` grouped by `reason_code`) — a spike in one `reason_code` (e.g. `unknown_meter`) usually means a reference-data gap (a new meter installed but not yet seeded — see Backfills above), not a Silver pipeline bug.
3. **DMA leak flags** (`gold.operational_dashboard.dma_leak_flag_count`, `gold.dma_analytics.night_flow_anomaly_flag`) — an operational (not engineering) signal; route to the utility's field operations team, not on-call engineering, unless the flag itself looks systematically wrong (e.g. every DMA flagged at once, suggesting a data issue rather than 20 simultaneous real leaks).
4. **System-table observability** (`sql/observability/`) — cost anomalies, query performance regressions, audit anomalies. Not real-time alerting (these are ad hoc/dashboard queries), so check them proactively, not just on page.

## Environment promotion

`dev → staging → prod`, per CONTRIBUTING.md — enforced by `bundle-deploy.yml`'s GitHub Environment reviewer gates on `staging`/`prod` (Settings → Environments). Terraform infrastructure changes go through `terraform-apply.yml` (manual `workflow_dispatch`, also environment-gated) — deliberately a separate, more manual trigger than the bundle deploy, since infra apply is the platform's highest-blast-radius action.
