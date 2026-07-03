# ADR-0011: Split Gold into a Continuous Pipeline (Hourly) and a Triggered Batch Pipeline (Daily Marts), with a Documented Non-Revenue-Water Proxy

## Status
Accepted

## Context
Phase 5 must build six Gold tables (`gold.hourly_consumption`, `gold.daily_usage`, `gold.dma_analytics`, `gold.customer_analytics`, `gold.operational_dashboard`, `gold.executive_dashboard`) from `silver.meter_readings`. Two independent design questions arise:

1. **Pipeline cadence.** ARCHITECTURE.md already states Gold should be "streaming where the KPI tolerates it (e.g. hourly consumption); batch/triggered where it doesn't (e.g. daily billing-adjacent aggregates that must wait for the day to fully close plus the late-arrival reconciliation window)" — but doesn't specify whether that means one pipeline with mixed-cadence flows, or separate pipelines.
2. **`gold.dma_analytics`' non-revenue-water calculation** requires comparing metered consumption against bulk/production supply volume. This platform ingests customer smart meter telemetry only (`schemas/avro/meter_telemetry.avsc`) — there is no bulk supply-meter/SCADA data source integrated into any phase of this repository. A real water-balance NRW figure is not computable from data this platform actually has.

Options considered for (1):
- **1a.** One Lakeflow pipeline containing both the streaming `hourly_consumption` flow and the batch daily marts
- **1b.** Two separate pipelines — one continuous (`gold_hourly_consumption`), one triggered (`gold_daily_marts`) — the triggered one scheduled via a wrapping Databricks Job

Options considered for (2):
- **2a.** Omit `dma_analytics`'/`executive_dashboard`'s supply/NRW columns entirely until a real bulk-supply integration exists
- **2b.** Compute an **estimated supply proxy** from `reference.dim_dma.target_nrw_pct` (`estimated_supply_liters = metered_consumption_liters / (1 - target_nrw_pct/100)`), clearly documented as a proxy, not real telemetry
- **2c.** Fabricate a plausible bulk-supply meter data source (a second synthetic Avro feed) to make the NRW figure "real" within this repository's synthetic world

## Decision
- **Pipeline cadence: 1b.** Two Lakeflow pipelines — `gold_hourly_consumption` (continuous) and `gold_daily_marts` (triggered, driven by a daily-scheduled Databricks Job task).
- **NRW: 2b.** `gold.dma_analytics`/`gold.executive_dashboard` carry an `estimated_supply_liters`/`*_nrw_*` proxy derived from `target_nrw_pct`, with `night_flow_anomaly_flag` implemented separately from real metered data as the actually-trustworthy leak indicator in the same table.

## Rationale

- **1b vs. 1a (one mixed-cadence pipeline)**: Lakeflow pipelines have a single top-level trigger mode (`continuous: true/false` in the bundle resource); achieving genuinely different cadences for different tables within one pipeline would mean either running the whole pipeline continuously (wasting compute continuously re-evaluating the batch marts' full-history recompute — see gold_daily_marts.py's docstring on why those are full materialized-view recomputes, not incremental) or running it triggered (delaying `hourly_consumption` to the same daily cadence as the marts, defeating the point of having an hourly KPI at all). Two pipelines cost a second DAB resource and a second Databricks Job to schedule the triggered one, but that's a small, one-time cost against getting the wrong cadence for either half of Gold.
- **1b's job-based scheduling**: pipeline resources in Databricks Asset Bundles have no native cron `schedule:` field (unlike Job resources) — a triggered pipeline is started either manually, via the UI/API, or via a Databricks Job's `pipeline_task`. `bundles/gold_batch_pipeline.yml`'s `gold_daily_marts_trigger` job exists for exactly this reason, scheduled at 05:00 UTC — after `silver_late_arrival_reconciliation`'s 03:00 UTC run (ADR-0010), so the previous day's readings have had a chance to settle before Gold recomputes from them.
- **2b vs. 2a (omit NRW entirely)**: `docs/architecture/ARCHITECTURE.md` explicitly names `gold.dma_analytics` as "DMA balance (supply vs. metered consumption → non-revenue water / leak indicators)" — shipping Phase 5 with that column silently missing would leave the table's stated purpose unmet with no visible signal *why*. A clearly-labeled proxy, with the exact formula and its data-provenance gap documented in the pipeline docstring, the DDL comment, and this ADR, is more useful than an empty column: it demonstrates the intended calculation shape (validated in `tests/unit/test_gold_transforms.py`) and is trivially swapped for a real supply feed later (the join point is `reference.dim_dma`, which a bulk-supply integration would extend or replace) — an omitted column would need a Silver/Gold schema change plus new pipeline logic built from scratch when that integration eventually happens, not just a formula swap.
- **2b vs. 2c (fabricate a synthetic bulk-supply feed)**: inventing a second synthetic data source purely to make a downstream number look "real" manufactures false confidence — a demo/test NRW figure computed from *invented* supply data is no more trustworthy than one computed from a documented formula, but is far more likely to be mistaken for genuine telemetry later (an invented Avro schema and mock generator look exactly like Bronze's real ingestion path). Being explicit that this is a proxy, in-code and in the DDL, is safer than manufacturing a fake but structurally "real-looking" data source.
- **Night-flow anomaly detection is kept independent of the supply proxy** specifically so `gold.dma_analytics` still delivers one genuinely trustworthy leak indicator (computed from real metered flow-rate data, no proxy involved) even though its NRW columns are not yet trustworthy for a real audit — the table isn't "half fake," it's "one proxy column family and one real one," and both are labeled as such.

## Consequences

- A real bulk-supply meter/SCADA integration (a new ADR when it happens) will need to either replace `estimated_supply_liters`'s formula with a real join, or add a distinct `actual_supply_liters` column alongside the proxy — `gold.dma_analytics`' DDL comment and this ADR are the pointer for whoever picks that up.
- `gold.daily_usage`, `gold.dma_analytics`, and `gold.customer_analytics` are implemented as full materialized-view recomputes over all of Silver's history on every triggered run (see `gold_daily_marts.py`'s docstring) rather than incrementally maintained — correct and simple at this repository's synthetic data volumes, but a real fleet-scale deployment computing trailing-window anomaly baselines over the platform's full multi-year Silver history daily would need an incremental/partition-scoped rewrite. Tracked here as a Phase 8 performance item, not solved in Phase 5.
- Operating two Gold pipelines (plus one scheduling Job) instead of one means two sets of pipeline-level monitoring/alerting to wire up in Phase 8, rather than one — an accepted, small increase in operational surface area for the cadence-correctness this decision buys.
