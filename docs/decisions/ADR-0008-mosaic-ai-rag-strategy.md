# ADR-0008: In-Workspace Mosaic AI (Vector Search + Model Serving) for AI/RAG Use Cases

## Status
Accepted

## Context
Phase 7 requires leak detection, demand forecasting, anomaly detection, predictive maintenance, an NL analytics assistant, and agentic AI over the platform's Gold/Silver data and documentation. These need model training/serving infrastructure and, for the NL assistant, a vector index for retrieval-augmented generation (RAG) grounded in KPI definitions, DMA metadata, and operational documentation.

Options considered:

1. **Mosaic AI** (Vector Search + Model Serving + MLflow), entirely inside the Databricks workspace, governed by Unity Catalog
2. **External vector database** (e.g. Pinecone, Weaviate) + externally hosted model endpoints (e.g. Azure OpenAI directly, bypassing Databricks Model Serving)
3. **Hybrid**: Databricks for training/feature engineering, external services for serving and vector search

## Decision
Use **Mosaic AI Vector Search** and **Mosaic AI Model Serving**, with **MLflow** as the experiment tracking and model registry, entirely within the Databricks workspace and governed by Unity Catalog. Azure OpenAI / other foundation models are accessed *through* Databricks' external-model serving endpoints (a governed proxy), not called directly from application code.

## Rationale

- **Governance boundary stays single**: the strongest reason to keep vector search and model serving in-workspace is that Unity Catalog's access control, lineage, and audit logging (ADR-0002, ADR-0006) then cover the AI surface too — a vector index is registered as a Unity Catalog object and inherits the same RBAC/ABAC as any table. An external vector DB would need its own, separately administered access control system, doubling the compliance surface this platform's governance investment is meant to avoid (see [security-diagram.md](../architecture/diagrams/security-diagram.md)).
- **No duplicated data movement/sync problem**: Mosaic AI Vector Search can build indexes directly from Unity Catalog Delta tables with managed sync (Delta CDF-driven incremental index updates). An external vector DB would require a custom sync pipeline (export → transform → upsert) that is itself a new failure mode and a new source of staleness between Gold data and what the AI assistant retrieves.
- **Model Serving as a governed proxy for external foundation models**: routing Azure OpenAI (or other external model) calls through Databricks' external-model serving endpoints means every AI call — whether to a Mosaic-trained model or a hosted foundation model — is subject to the same request/response logging, rate limiting, and Unity Catalog permission model, rather than embedding API keys and making direct calls from scattered application code.
- **MLflow as the one experiment/model registry**: avoids a second model registry (e.g. a cloud-native ML platform's own registry) with its own versioning and promotion workflow running in parallel to the one already tracking Silver/Gold-adjacent feature engineering work.

## Consequences

- The platform takes a dependency on Mosaic AI feature availability/maturity for each AI use case (leak detection, forecasting, anomaly detection, RAG, agents) rather than picking best-of-breed point solutions per use case — accepted because the governance and data-locality benefits compound across *all* five AI use cases simultaneously, which a per-use-case "pick the best tool" approach would forfeit for each one individually.
- Vector index freshness is bounded by the sync schedule between Gold/documentation sources and the index (Phase 7 will define this per use case — near-real-time for operational alerts, daily for KPI/glossary grounding).
- Cost is attributed to and controlled by the same Serverless-first strategy as the rest of the platform (ADR-0007) — Model Serving endpoints scale to zero for non-latency-critical use cases, with minimum provisioned throughput reserved only for endpoints backing real-time operational alerts (e.g. leak detection scoring in the streaming path).
