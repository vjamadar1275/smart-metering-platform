# ADR-0002: Medallion Architecture on Delta Lake, Governed by Unity Catalog

## Status
Accepted

## Context
The platform needs one architecture that serves both continuous streaming ingestion and historical batch analytics, supports replay/reprocessing when business logic changes, and provides enterprise-grade governance (lineage, access control, audit) across every layer — without maintaining two parallel systems.

Options considered:

1. **Medallion architecture (Bronze/Silver/Gold) on Delta Lake, Unity Catalog-governed**
2. **Lambda architecture** — separate batch layer (e.g. ADLS + Spark batch jobs) and speed layer (e.g. Event Hubs + Stream Analytics), merged at serving time
3. **Flat data warehouse** — land directly into a modeled star schema (e.g. Synapse dedicated pool), skipping a raw/lakehouse tier

## Decision
**Medallion architecture on Delta Lake**, with **Unity Catalog** as the single governance plane across Bronze, Silver, and Gold.

## Rationale

- **vs. Lambda**: Lambda requires the same business logic to be implemented twice (once in the speed layer, once in the batch layer) and reconciled at query time — a well-known maintenance and consistency burden. Structured Streaming on Delta Lake (this platform's actual mechanism) already unifies batch and streaming under one API and one storage format, so Lambda's core justification (streaming and batch engines are fundamentally different) doesn't hold here.
- **vs. flat warehouse**: landing directly into a modeled schema destroys the raw signal needed to reprocess when a transformation bug is found or a new KPI is defined retroactively — the only "undo" is re-ingesting from the field, and Event Hub retention (max 90 days even on Dedicated) makes that impossible beyond that window. Bronze exists specifically to be the durable, replayable raw source so Silver/Gold logic can evolve without a re-ingestion dependency.
- **Three layers, not two or four**: see the trade-off table in [ARCHITECTURE.md § Medallion Architecture Design](../architecture/ARCHITECTURE.md#medallion-architecture-design). Two layers conflates "raw" and "cleansed," forcing every consumer to re-derive validation logic; a fourth layer (e.g. separate staging) adds pipeline hops without a correctness or performance win Lakeflow's Bronze/Silver/Gold conventions don't already provide.
- **Unity Catalog as the single governance plane**: without it, RBAC/lineage/audit would need to be implemented per-layer or per-consuming-application (Power BI row-level security, a separate ML feature-access system, etc.), multiplying the compliance surface. Unity Catalog's three-level namespace (`catalog.schema.table`) governs Bronze, Silver, Gold, feature tables, and the vector search index uniformly, and its automatic column-level lineage gives auditors a single place to answer "where did this number in the executive dashboard come from."

## Consequences

- All three layers must live in Delta format — this rules out, e.g., landing Bronze as plain Parquet/JSON for a marginal ingestion-speed gain, because it would forfeit Delta's ACID MERGE (needed for Silver dedup) and CDF (needed for incremental Silver→Gold and for AI feature pipelines).
- Every new table, regardless of layer, must be registered in Unity Catalog before use — enforced organizationally (Phase 2 workspace policy) since Unity Catalog has no fallback "ungoverned" table creation path once Unity Catalog is the workspace's only supported metastore mode.
- Reprocessing Silver/Gold from Bronze is a supported, expected operation (used when validation logic changes) — pipelines must be idempotent (MERGE-based, not append-only) to make this safe, which is why Silver/Gold use MERGE semantics rather than blind appends.
