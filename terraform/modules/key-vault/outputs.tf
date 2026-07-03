output "key_vault_id" {
  description = "Resource ID of the Key Vault."
  value       = null # populated in Phase 2
}

output "vault_uri" {
  description = "Vault URI, used by Databricks secret scopes and ADLS/Databricks CMK configuration."
  value       = null # populated in Phase 2
}
