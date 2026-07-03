# Module: monitoring

Provisions the Log Analytics Workspace, diagnostic settings (for Databricks, Event Hubs, ADLS, Key Vault), and Azure Monitor alert rules feeding Lakehouse Monitoring / system-table-based observability described in the (Phase 8) Monitoring section.

**Status**: interface defined (Phase 1); resources implemented in Phase 8 (monitoring is deployed alongside the workloads it observes as each phase lands, but the shared Log Analytics workspace and alert plumbing are hardened in Phase 8).
