output "resource_group_names" {
  description = "Names of the resource groups created for this environment."
  value = {
    network    = azurerm_resource_group.network.name
    data       = azurerm_resource_group.data.name
    databricks = azurerm_resource_group.databricks.name
    monitoring = azurerm_resource_group.monitoring.name
  }
}

output "standard_tags" {
  description = "The standard tag set applied to all resources in this environment, for reuse by CI/CD tooling."
  value       = local.standard_tags
}

output "vnet_id" {
  description = "VNet resource ID, for peering or reference from other environments' tooling."
  value       = module.networking.vnet_id
}

output "databricks_workspace_url" {
  description = "Workspace URL."
  value       = module.databricks_workspace.workspace_url
}

output "catalog_name" {
  description = "Unity Catalog catalog name created for this environment."
  value       = module.unity_catalog.catalog_name
}
