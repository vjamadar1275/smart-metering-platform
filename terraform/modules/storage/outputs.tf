output "storage_account_id" {
  description = "Resource ID of the ADLS Gen2 storage account."
  value       = azurerm_storage_account.this.id
}

output "storage_account_name" {
  description = "Name of the storage account."
  value       = azurerm_storage_account.this.name
}

output "primary_dfs_endpoint" {
  description = "Primary Data Lake (dfs) endpoint, used as the base path for external locations in Unity Catalog."
  value       = azurerm_storage_account.this.primary_dfs_endpoint
}

output "container_ids" {
  description = "Map of container name to resource ID."
  value       = { for k, v in azurerm_storage_container.this : k => v.resource_manager_id }
}
