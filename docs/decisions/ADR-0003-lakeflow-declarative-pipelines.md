# ADR-0003: Lakeflow Declarative Pipelines for Silver/Gold Transformations

## Status
Accepted

## Context
Silver and Gold transformations need data quality enforcement, dependency management between tables, automatic handling of incremental processing, and pipeline-level observability — at a scale (billions of records/day) where hand-rolled orchestration bugs are expensive to discover late.

Options considered:

1. **Lakeflow Declarative Pipelines** (Databricks' managed declarative ETL framework, successor to Delta Live Tables)
2. **Hand-rolled Structured Streaming / batch Spark jobs**, orchestrated as a DAG of plain Databricks Jobs tasks
3. **Third-party orchestration** (e.g. Apache Airflow on top of plain Spark jobs)

## Decision
Use **Lakeflow Declarative Pipelines** for Bronze→Silver and Silver→Gold, with Databricks Jobs used only as the outer scheduler that triggers pipeline updates and non-pipeline tasks (e.g. ML training, report generation).

## Rationale

- **Data quality as a first-class primitive**: Lakeflow *Expectations* (`expect`, `expect_or_drop`, `expect_or_fail`) let validation rules live next to the transformation they gate, and automatically produce quality metrics per rule — the hand-rolled alternative means building and maintaining a custom rules engine and metrics emitter, duplicating what Lakeflow already provides.
- **Automatic dependency resolution**: Lakeflow infers the Bronze→Silver→Gold DAG from table read/write dependencies in code, so adding a new Gold table that depends on an existing Silver table doesn't require manually wiring a new Jobs task dependency — reducing the chance of a misconfigured DAG causing a table to be read before its upstream dependency has committed.
- **Unified batch + streaming pipeline definition**: the same pipeline framework handles the continuous Bronze/Silver streaming tables and the triggered/batch Gold aggregation tables, avoiding two separate orchestration systems for what is conceptually one pipeline.
- **vs. Airflow**: Airflow adds a second scheduling system and a second place operational knowledge must live (DAG files, Airflow-specific retries/SLAs) for logic that Databricks Jobs + Lakeflow already schedule, retry, and alert on natively, with tighter integration into Unity Catalog lineage and Databricks' own monitoring surfaces. Airflow remains a reasonable choice only if this platform needed to orchestrate significant non-Databricks work (e.g. cross-cloud); it doesn't.

## Consequences

- Transformation logic is expressed in Lakeflow's Python/SQL declarative API rather than arbitrary PySpark control flow — most Silver/Gold logic fits this model cleanly (it's fundamentally a series of typed transformations), but any genuinely imperative logic (e.g. a complex stateful session-windowing algorithm) may need to be isolated into a plain Structured Streaming job outside Lakeflow and fed back in as a source table.
- The team must adopt Lakeflow's development workflow (pipeline development mode, expectations-driven testing) rather than a fully custom test harness — this is treated as a net positive for consistency but is a real onboarding cost, addressed in the Phase 8 Developer Guide.
- Pipeline-level monitoring (event log, data quality metrics) is Lakeflow-native; Phase 8's Lakehouse Monitoring and alerting build on top of it rather than replacing it.
