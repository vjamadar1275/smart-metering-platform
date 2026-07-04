# Performance Guide

Sizing methodology, what's been benchmarked so far (and what hasn't), and tuning playbooks.

## Sizing methodology

1. Start from the [capacity plan](../architecture/ARCHITECTURE.md#capacity-planning) (events/sec, storage growth) — every module's default sizing (Event Hub partitions, SQL Warehouse cluster counts, Bronze's `maxOffsetsPerTrigger`) traces back to those numbers, scaled per environment (dev: functional-testing subset; staging: production-representative; prod: current scale + headroom toward the 100M-meter design target).
2. Deploy to a real environment and let it run under representative load (`tools/event_hub_simulator/`, `tests/load/`).
3. Measure against `sql/observability/warehouse_query_performance.sql` (SQL Warehouse p95/failure rate) and the Databricks pipeline event log (streaming lag, batch duration) — **not done yet** in this repository, since it requires a live workspace this sandboxed development environment doesn't have.
4. Adjust sizing (warehouse cluster counts, `bronze_max_offsets_per_trigger`, Gold batch pipeline's cluster policy) based on step 3's real measurements, not the step-1 capacity plan alone — the capacity plan is a starting estimate, not a substitute for measuring the real thing.

**This repository has only completed step 1.** Steps 2-4 require applying Terraform and deploying the bundle to a real workspace, which is explicitly out of scope for this repository's local development (see `terraform/README.md`) — the first real platform admin to apply this infrastructure should treat steps 2-4 as their immediate next task, not assume this guide's numbers are already validated.

## What IS benchmarked (locally, in this repository)

`tests/performance/test_transform_benchmarks.py` — Gold/ML transform functions at ~45K-row synthetic scale on local single-executor PySpark. These are regression tripwires (catch an accidental algorithmic blowup), not sizing data — a function passing its local time budget says nothing about how it performs on a real cluster against real data volume. See that test file's own docstring.

## Known scaling gaps (documented, not solved)

- **`tools/mock_data_generator/generator.py`'s `generate_meter_master`** builds its population as a single in-memory Python list on the driver — does not scale to literal fleet-size (10M+) meter counts. `src/config/staging/seed_reference_data_job.json` already caps staging's synthetic seed at 100,000 meters for this reason. A distributed rewrite (Spark `range()` + a pandas UDF) would be needed to seed a literal fleet-scale synthetic population — not needed for validating pipeline logic at the scale this repository currently seeds.
- **`gold.daily_usage`/`gold.dma_analytics`/`gold.customer_analytics`** (`src/pipelines/gold/gold_daily_marts.py`) are full materialized-view recomputes over all of Silver's history on every triggered run, not incrementally maintained — correct and simple at this repository's synthetic data volumes (see ADR-0011's consequence), but a real fleet-scale deployment recomputing trailing-window anomaly baselines over a full multi-year Silver history daily would need an incremental/partition-scoped rewrite.
- **SQL Warehouse sizing** (`terraform/modules/sql-warehouse/README.md`'s table) is a starting point explicitly flagged as needing revision once real query patterns are measured (ADR-0005's consequence) — not yet done, per this guide's methodology section above.

## Tuning playbook: streaming lag

If Bronze/Silver/Gold-hourly streaming lag grows:
1. Check `bronze_max_offsets_per_trigger` (`src/config/<env>/bronze_pipeline.json`) against actual Event Hub throughput — too low a value bottlenecks catch-up after any outage; too high risks large, slow micro-batches.
2. Check Serverless compute isn't being throttled by a workspace-level concurrency/cost policy (Databricks account console).
3. For Silver specifically: verify the AUTO CDC MERGE isn't blocked by a concurrent write from `silver_late_arrival_reconciliation.py`'s nightly batch job (ADR-0010's documented, accepted conflict risk) — a genuine conflict fails cleanly and is safe to retry, but frequent conflicts suggest the reconciliation job's 03:00 UTC schedule needs to move to a lower-traffic window for your actual traffic pattern.

## Tuning playbook: SQL Warehouse query latency

1. `sql/observability/warehouse_query_performance.sql` — check p95 duration and failed-query rate per warehouse.
2. If `sqlw-bi`/`sqlw-executive` show elevated latency correlated with `sqlw-adhoc` load spikes, ADR-0005's workload isolation isn't actually preventing contention as designed — check `sqlw-adhoc`'s `max_clusters` ceiling isn't being hit (queueing within that warehouse can still show as latency, even though it's isolated from the other two).
3. If a single warehouse's own queries are slow regardless of other warehouses' load: check Gold table Liquid Clustering keys (ADR-0004) still match actual query filter columns — a query pattern that's shifted away from the clustering key benefits far less from clustering, per ADR-0004's consequence about revisiting clustering keys.
