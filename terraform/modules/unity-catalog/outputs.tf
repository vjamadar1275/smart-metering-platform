output "metastore_id" {
  description = "Resource ID of the Unity Catalog metastore (whether created or attached)."
  value       = null # populated in Phase 2
}

output "catalog_id" {
  description = "Fully-qualified name of the catalog created for this environment."
  value       = null # populated in Phase 2
}

output "schema_ids" {
  description = "Map of schema name to fully-qualified schema identifier."
  value       = {} # populated in Phase 2
}

output "storage_credential_id" {
  description = "ID of the storage credential used by this catalog's external location."
  value       = null # populated in Phase 2
}
