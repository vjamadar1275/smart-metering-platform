output "storage_account_id" {
  description = "Resource ID of the ADLS Gen2 storage account."
  value       = null # populated in Phase 2
}

output "primary_dfs_endpoint" {
  description = "Primary Data Lake (dfs) endpoint, used as the base path for external locations in Unity Catalog."
  value       = null # populated in Phase 2
}

output "container_ids" {
  description = "Map of container name to resource ID."
  value       = {} # populated in Phase 2
}
