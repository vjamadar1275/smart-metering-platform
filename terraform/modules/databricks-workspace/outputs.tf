output "workspace_id" {
  description = "Resource ID of the Databricks workspace."
  value       = azurerm_databricks_workspace.this.id
}

output "workspace_url" {
  description = "Workspace URL, used to configure the databricks provider for workspace-level resources (e.g. Unity Catalog grants, SQL Warehouses)."
  value       = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "workspace_id_numeric" {
  description = "Numeric workspace ID, required for account-level Unity Catalog workspace-binding."
  value       = azurerm_databricks_workspace.this.workspace_id
}
