# Module: managed-identity

Provisions one User-Assigned Managed Identity per workload (Bronze pipeline, Silver pipeline, Gold pipeline, Model Serving, CI/CD deployment) per [ADR-0007](../../../docs/decisions/ADR-0007-compute-strategy.md) and [security-diagram.md](../../../docs/architecture/diagrams/security-diagram.md) — no shared credentials between workloads.

**Status**: interface defined (Phase 1); resources implemented in Phase 2.
