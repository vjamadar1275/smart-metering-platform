output "identity_ids" {
  description = "Map of workload name to Managed Identity resource ID."
  value       = { for k, v in azurerm_user_assigned_identity.this : k => v.id }
}

output "principal_ids" {
  description = "Map of workload name to Entra principal (object) ID, used for RBAC/Key Vault access policy assignment."
  value       = { for k, v in azurerm_user_assigned_identity.this : k => v.principal_id }
}

output "client_ids" {
  description = "Map of workload name to client (application) ID."
  value       = { for k, v in azurerm_user_assigned_identity.this : k => v.client_id }
}
