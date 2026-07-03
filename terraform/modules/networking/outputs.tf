output "vnet_id" {
  description = "Resource ID of the VNet."
  value       = azurerm_virtual_network.this.id
}

output "subnet_ids" {
  description = "Map of subnet purpose to subnet resource ID."
  value = {
    databricks_public  = azurerm_subnet.databricks_public.id
    databricks_private = azurerm_subnet.databricks_private.id
    private_endpoints  = azurerm_subnet.private_endpoints.id
  }
}

output "subnet_names" {
  description = "Map of subnet purpose to subnet name, required by the databricks-workspace module's VNet-injection custom_parameters (which take names, not IDs)."
  value = {
    databricks_public  = azurerm_subnet.databricks_public.name
    databricks_private = azurerm_subnet.databricks_private.name
  }
}

output "nsg_ids" {
  description = "Map of subnet purpose to associated NSG resource ID."
  value = {
    databricks_public  = azurerm_network_security_group.databricks_public.id
    databricks_private = azurerm_network_security_group.databricks_private.id
  }
}

output "nsg_association_ids" {
  description = "Map of subnet purpose to the azurerm_subnet_network_security_group_association resource ID — this, not the NSG ID itself, is what the databricks-workspace module's custom_parameters requires (it sequences NSG association before workspace creation)."
  value = {
    databricks_public  = azurerm_subnet_network_security_group_association.databricks_public.id
    databricks_private = azurerm_subnet_network_security_group_association.databricks_private.id
  }
}

output "private_dns_zone_ids" {
  description = "Map of privatelink DNS zone name to resource ID, for linking from dependent modules."
  value       = { for k, v in azurerm_private_dns_zone.this : k => v.id }
}

output "firewall_private_ip" {
  description = "Private IP of the Azure Firewall, used as the next hop in route tables (if enabled)."
  value       = var.enable_firewall ? azurerm_firewall.this[0].ip_configuration[0].private_ip_address : null
}
