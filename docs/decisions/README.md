# Architecture Decision Records

Each ADR documents one significant, hard-to-reverse decision: the alternatives considered, why the chosen option won, and what it costs us. Numbered sequentially; never renumbered or deleted — a superseded decision gets a new ADR that says so and links back.

| ADR | Title |
|---|---|
| [0001](ADR-0001-event-hub-vs-alternatives.md) | Azure Event Hubs (Dedicated Tier) for Telemetry Ingestion |
| [0002](ADR-0002-medallion-unity-catalog.md) | Medallion Architecture on Delta Lake, Governed by Unity Catalog |
| [0003](ADR-0003-lakeflow-declarative-pipelines.md) | Lakeflow Declarative Pipelines for Silver/Gold Transformations |
| [0004](ADR-0004-liquid-clustering.md) | Liquid Clustering (Not Static Partitioning) on Silver/Gold Tables |
| [0005](ADR-0005-sql-warehouse-isolation.md) | Workload-Isolated SQL Warehouses |
| [0006](ADR-0006-unity-catalog-strategy.md) | Catalog-per-Environment, Schema-per-Domain Unity Catalog Strategy |
| [0007](ADR-0007-compute-strategy.md) | Serverless-First Compute, Job Clusters for Scheduled ETL |
| [0008](ADR-0008-mosaic-ai-rag-strategy.md) | In-Workspace Mosaic AI (Vector Search + Model Serving) for AI/RAG Use Cases |
| [0009](ADR-0009-event-hub-connector-protocol.md) | Kafka Protocol for Spark Consumption, Native AMQP for Producers |
| [0010](ADR-0010-silver-dedup-and-late-arrival-strategy.md) | Bounded-Watermark Streaming Dedup (AUTO CDC) + Nightly Batch Reconciliation for Late Arrivals |

New ADRs are added as later phases (streaming design, ML model choices, CI/CD gating strategy, etc.) reach decisions worth recording.
