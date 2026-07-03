output "vnet_id" {
  description = "Resource ID of the VNet."
  value       = null # populated in Phase 2
}

output "subnet_ids" {
  description = "Map of subnet purpose to subnet resource ID."
  value       = {} # populated in Phase 2
}

output "nsg_ids" {
  description = "Map of subnet purpose to associated NSG resource ID."
  value       = {} # populated in Phase 2
}

output "private_dns_zone_ids" {
  description = "Map of privatelink DNS zone name to resource ID, for linking from dependent modules."
  value       = {} # populated in Phase 2
}

output "firewall_private_ip" {
  description = "Private IP of the Azure Firewall, used as the next hop in route tables (if enabled)."
  value       = null # populated in Phase 2
}
