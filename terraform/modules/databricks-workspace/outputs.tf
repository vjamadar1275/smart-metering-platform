output "workspace_id" {
  description = "Resource ID of the Databricks workspace."
  value       = null # populated in Phase 2
}

output "workspace_url" {
  description = "Workspace URL, used to configure the databricks provider for workspace-level resources (e.g. Unity Catalog grants, SQL Warehouses)."
  value       = null # populated in Phase 2
}

output "workspace_id_numeric" {
  description = "Numeric workspace ID, required for account-level Unity Catalog workspace-binding."
  value       = null # populated in Phase 2
}
