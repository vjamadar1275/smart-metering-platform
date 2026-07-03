output "identity_ids" {
  description = "Map of workload name to Managed Identity resource ID."
  value       = {} # populated in Phase 2
}

output "principal_ids" {
  description = "Map of workload name to Entra principal (object) ID, used for RBAC/Key Vault access policy assignment."
  value       = {} # populated in Phase 2
}

output "client_ids" {
  description = "Map of workload name to client (application) ID."
  value       = {} # populated in Phase 2
}
