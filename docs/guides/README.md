# Guides

Operational and developer documentation, added as the phases they document are implemented — a guide describing code that doesn't exist yet would go stale immediately, so each is written alongside its subject matter rather than stubbed in advance.

| Guide | Added in | Covers |
|---|---|---|
| Developer Guide | Phase 3–5 | Local setup, coding standards, testing conventions, PR workflow |
| Deployment Guide | Phase 2 | Terraform bootstrap, environment promotion, Databricks Asset Bundle deployment |
| Operations Guide | Phase 8 | Day-2 operations: pipeline restarts, backfills, scaling, on-call |
| Security Guide | Phase 8 | Key rotation, access reviews, incident response, compliance evidence |
| Performance Guide | Phase 8 | Benchmarks, sizing methodology, tuning playbooks |
| Troubleshooting Guide | Phase 8 | Common failure modes and their resolutions across the pipeline |
| API Documentation | Phase 7 | Model Serving endpoint contracts, agent/RAG API surface |

Until then, [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) and the [ADRs](../decisions/) are the authoritative reference for how the platform is designed and why.
