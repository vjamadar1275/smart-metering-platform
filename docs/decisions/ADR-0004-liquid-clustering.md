# ADR-0004: Liquid Clustering (Not Static Partitioning) on Silver/Gold Tables

## Status
Accepted

## Context
At 960M–9.6B records/day, Silver and Gold tables need physical layout that supports efficient pruning for the platform's dominant query patterns (by meter, by DMA, by time range, by customer) without the operational burden of manually choosing and re-choosing partition/Z-order keys as query patterns evolve, and without the small-file and partition-skew problems Hive-style partitioning produces at high cardinality.

Options considered:

1. **Liquid Clustering** on Silver/Gold, with Predictive Optimization managing `OPTIMIZE`/`VACUUM`
2. **Hive-style static partitioning** (e.g. by `ingest_date`) + manual `OPTIMIZE ZORDER BY` jobs
3. **No clustering** — rely on file-level statistics and Photon's scan efficiency alone

## Decision
Use **Liquid Clustering** on Silver and Gold tables, clustered on the columns each table is actually queried by (e.g. `(meter_id, reading_date)` for Silver, `(dma_id, usage_date)` for `gold.dma_analytics`), with **Predictive Optimization** enabled at the catalog level to automate maintenance.

## Rationale

- **vs. static date partitioning**: date partitioning alone doesn't help the platform's second-most-common access pattern — "all readings for meter X" or "all meters in DMA Y" — without an additional Z-order pass. At 10M+ distinct meter IDs, partitioning *by* meter_id would create far too many small partitions (a classic Hive anti-pattern); Liquid Clustering solves this because it doesn't require partition-column cardinality to stay low — it clusters at the file level using a different underlying strategy that tolerates high-cardinality keys.
- **Clustering keys can change without a full table rewrite**: as Gold marts evolve (new KPI, new dominant filter column) a Hive-partitioned table would require a full data rewrite to change the partition column. Liquid Clustering allows the clustering key to be altered and applied incrementally by future `OPTIMIZE` runs, which matters given this platform's Gold layer is expected to grow new marts over Phases 5–8.
- **Predictive Optimization removes a scheduling problem, not just a manual command**: manually scheduled `OPTIMIZE`/`VACUUM` jobs are either too infrequent (query performance degrades as small files accumulate between runs) or too frequent (wasted compute re-optimizing already-well-clustered data). Predictive Optimization observes actual table write/read patterns and schedules maintenance accordingly, which is particularly valuable here because Bronze/Silver ingestion rate is continuous and variable (peak vs. off-peak), not a fixed batch cadence a manual schedule could easily match.

## Consequences

- Liquid Clustering requires Databricks Runtime versions that support it (current LTS at time of writing) — a runtime-version floor is now part of the cluster policy (Phase 2/8).
- Clustering key choice still requires a deliberate decision per table, informed by actual query patterns — this is captured per-table in the DDL comments under `sql/ddl/` (Phase 5+) rather than being a "set once, ignore forever" choice; clustering keys should be revisited if Lakehouse Monitoring (Phase 8) shows query patterns have shifted.
- Bronze retains simple `ingest_date` partitioning rather than Liquid Clustering — Bronze is append-only and almost exclusively scanned by ingest-date range (for Silver's incremental read and for replay), so date partitioning is sufficient and cheaper to maintain than clustering a raw, immutable layer.
