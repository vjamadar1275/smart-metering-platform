# Module: monitoring

Provisions the Log Analytics Workspace, diagnostic settings (for Databricks, Event Hubs, ADLS, Key Vault), a shared Azure Monitor action group, and a baseline pipeline/job-failure alert rule feeding the centralized observability described in [security-diagram.md](../../../docs/architecture/diagrams/security-diagram.md)'s Audit & Compliance layer.

**Status**: implemented (Phase 8). See `terraform/environments/<env>/main.tf` for the module call — `diagnostic_target_resource_ids` is wired to that environment's Databricks workspace, Event Hub namespace, storage account, and Key Vault IDs.

This module covers **Azure-side** observability (resource logs/metrics, action groups, alert rules). **Databricks-native** observability — Lakehouse Monitoring on Gold tables and system-table-based cost/usage/lineage queries — is set up separately via `src/jobs/create_lakehouse_monitors.py` and `sql/observability/` (Unity Catalog objects, not Azure resources, so out of Terraform's scope) — see that job's docstring and [docs/guides/OPERATIONS_GUIDE.md](../../../docs/guides/OPERATIONS_GUIDE.md).

## Resource-specific diagnostic tables

`log_analytics_destination_type = "Dedicated"` routes each monitored resource's logs into their own resource-specific table (e.g. Databricks workspace diagnostics land in `DatabricksJobs`, `DatabricksClusters`, etc.) rather than the shared `AzureDiagnostics` table — this is what the baseline `pipeline_failures` alert rule's KQL query targets directly.

