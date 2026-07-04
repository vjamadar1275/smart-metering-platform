-- System-table-based cost observability (Phase 8) — reference query, run
-- directly against Databricks system tables (system.billing.usage). No
-- setup required (system tables are enabled by default on Unity
-- Catalog-enabled workspaces since account-level system table access is
-- granted) beyond USE CATALOG system permission for the querying
-- principal.
--
-- Scoped to this platform's compute via the resource tags Terraform
-- applies everywhere (project = "smart-metering-platform") plus the
-- catalog-per-environment boundary (ADR-0006) — usage_metadata carries
-- the workspace/warehouse/job IDs system.billing.usage bills against.

SELECT
    date_trunc('day', usage_date) AS usage_day,
    sku_name,
    usage_unit,
    sum(usage_quantity) AS total_usage_quantity
FROM system.billing.usage
WHERE
    usage_date >= date_sub(current_date(), 30)
    AND custom_tags['project'] = 'smart-metering-platform'
GROUP BY ALL
ORDER BY usage_day DESC, total_usage_quantity DESC;
