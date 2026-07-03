output "key_vault_id" {
  description = "Resource ID of the Key Vault."
  value       = azurerm_key_vault.this.id
}

output "vault_uri" {
  description = "Vault URI, used by Databricks secret scopes and ADLS/Databricks CMK configuration."
  value       = azurerm_key_vault.this.vault_uri
}

output "key_vault_name" {
  description = "Name of the Key Vault, required by the Databricks secret-scope-backed-by-Key-Vault resource (which takes name + resource ID)."
  value       = azurerm_key_vault.this.name
}
