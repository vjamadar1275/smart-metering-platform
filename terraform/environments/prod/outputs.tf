output "resource_group_names" {
  description = "Names of the primary-region resource groups created for this environment."
  value = {
    network    = azurerm_resource_group.network.name
    data       = azurerm_resource_group.data.name
    databricks = azurerm_resource_group.databricks.name
    monitoring = azurerm_resource_group.monitoring.name
  }
}

output "dr_resource_group_names" {
  description = "Names of the secondary-region (DR) resource groups, if enabled."
  value = var.enable_dr_region ? {
    data       = azurerm_resource_group.dr_data[0].name
    databricks = azurerm_resource_group.dr_databricks[0].name
  } : null
}

output "standard_tags" {
  description = "The standard tag set applied to all resources in this environment, for reuse by CI/CD tooling."
  value       = local.standard_tags
}
