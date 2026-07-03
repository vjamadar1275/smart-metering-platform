output "metastore_id" {
  description = "Resource ID of the Unity Catalog metastore (newly created if create_metastore is true, otherwise echoes existing_metastore_id). Read by other environments' terraform_remote_state to attach to a shared metastore."
  value       = local.metastore_id
}

output "catalog_name" {
  description = "Fully-qualified name of the catalog created for this environment."
  value       = databricks_catalog.this.name
}

output "schema_names" {
  description = "List of schema names created within the catalog."
  value       = [for s in databricks_schema.this : s.name]
}

output "storage_credential_name" {
  description = "Name of the storage credential used by this catalog's external location."
  value       = databricks_storage_credential.this.name
}

output "access_connector_id" {
  description = "Resource ID of the Azure Databricks Access Connector backing Unity Catalog's ADLS access."
  value       = azurerm_databricks_access_connector.this.id
}
