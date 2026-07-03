# Enterprise Smart Metering Data Platform

A production-grade Lakehouse platform on **Azure Databricks** for a water utility operating **10 million smart meters** (designed to scale to **100 million**), each reporting telemetry every 15 minutes. The platform delivers continuous streaming ingestion, near-real-time and historical analytics, AI-powered insights (leak detection, demand forecasting, anomaly detection), and enterprise governance — at billions-of-records scale, with zero data loss and cost efficiency as first-class requirements.

This repository is built and delivered **incrementally by phase**. Each phase is fully implemented, tested, and documented before the next begins. See [Delivery Phases](#delivery-phases) for status.

---

## Business Scale Targets

| Metric | Today | Design target |
|---|---|---|
| Connected meters | 10,000,000 | 100,000,000 |
| Reporting interval | 15 minutes | 15 minutes |
| Readings/day (10M meters) | 960,000,000 | — |
| Readings/day (100M meters) | — | 9,600,000,000 |
| Average ingress rate | ~11,100 events/sec | ~111,000 events/sec |
| Data loss tolerance | Zero | Zero |
| Availability target | 99.9% (regional), 99.95% (paired-region DR) | Same |

Sizing, partitioning, and cost calculations throughout `docs/architecture/` are derived from these figures — see [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md#capacity-planning).

## Technology Stack

| Layer | Technology |
|---|---|
| Cloud | Microsoft Azure |
| Streaming ingestion | Azure Event Hubs (Dedicated tier) |
| Storage | Azure Data Lake Storage Gen2 |
| Compute / Lakehouse | Azure Databricks (Photon, Serverless + Job Clusters) |
| Table format | Delta Lake (Liquid Clustering, Change Data Feed, Deletion Vectors) |
| Pipelines | Lakeflow Declarative Pipelines |
| Governance | Unity Catalog (RBAC, ABAC, row/column security, lineage) |
| Analytics compute | Databricks SQL Warehouses (workload-isolated) |
| BI | Power BI (Direct Lake / DirectQuery) |
| AI/ML | Mosaic AI, MLflow, Vector Search, Model Serving |
| IaC | Terraform |
| CI/CD | GitHub Actions + Databricks Asset Bundles |
| Languages | Python, PySpark, SQL |

## Repository Structure

```
smart-metering-platform/
├── docs/                      Architecture, decisions (ADRs), guides, runbooks
│   ├── architecture/          High/low-level architecture + diagrams
│   ├── decisions/             Architecture Decision Records (ADR-NNNN)
│   ├── guides/                Developer / Operations / Security / Performance guides
│   └── runbooks/              Operational runbooks (incident response, DR failover, etc.)
├── terraform/                 Infrastructure as Code
│   ├── environments/          dev / staging / prod root configurations
│   └── modules/                networking, storage, key-vault, managed-identity, event-hub,
│                               databricks-workspace, unity-catalog, sql-warehouse, monitoring
├── src/
│   ├── pipelines/              bronze / silver / gold Lakeflow pipeline definitions
│   ├── libs/                   shared Python libraries (io, quality, monitoring, common)
│   ├── ml/                     Mosaic AI / MLflow model + agent code
│   ├── jobs/                   Databricks job orchestration (Asset Bundle resources)
│   └── config/                 per-environment configuration (dev/staging/prod)
├── sql/                        DDL for Unity Catalog objects, dashboard SQL
├── power_bi/                   Power BI semantic models / .pbip source
├── bundles/                    Databricks Asset Bundle definitions
├── tests/                      unit / integration / performance / load tests
├── tools/                      mock data generator, Event Hub simulator
└── .github/workflows/          CI/CD pipelines
```

## Delivery Phases

| Phase | Scope | Status |
|---|---|---|
| **1** | Repository structure, architecture, foundational Terraform, core docs | ✅ In progress (this commit) |
| 2 | Infrastructure: Databricks workspace, Unity Catalog, networking | ⬜ Not started |
| 3 | Streaming ingestion: Event Hubs → Structured Streaming → Bronze | ⬜ Not started |
| 4 | Silver: cleansing, validation, dedup, enrichment, watermarking | ⬜ Not started |
| 5 | Gold: business KPIs, DMA analytics, customer analytics | ⬜ Not started |
| 6 | SQL Warehouses, dashboards, Power BI | ⬜ Not started |
| 7 | Mosaic AI: leak detection, forecasting, anomaly detection, RAG/agents | ⬜ Not started |
| 8 | Security hardening, governance, monitoring, CI/CD, production readiness | ⬜ Not started |

## Getting Started (Phase 1)

Phase 1 ships architecture and IaC scaffolding only — no cloud resources are created yet (Phase 2 will `apply` real infrastructure).

```bash
# Review the architecture first
open docs/architecture/ARCHITECTURE.md

# Validate Terraform scaffolding formatting/syntax (no backend configured yet)
cd terraform/environments/dev
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## Documentation

- [Architecture Guide](docs/architecture/ARCHITECTURE.md) — high/low-level design, diagrams, capacity planning, trade-offs
- [Architecture Decision Records](docs/decisions/) — why each major choice was made, and the alternatives rejected
- Developer / Operations / Security / Performance guides — added as the phases that they document are implemented

## License / Ownership

Internal enterprise platform. Not licensed for external distribution.
