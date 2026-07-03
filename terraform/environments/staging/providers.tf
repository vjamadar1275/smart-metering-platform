provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }

  subscription_id = var.subscription_id
  storage_use_azuread = true
}

provider "azuread" {}

provider "databricks" {
  # Phase 2: configured for account-level (Unity Catalog metastore, workspace creation)
  # via azure_client_id / azure_client_secret / azure_tenant_id sourced from Key Vault-backed
  # environment variables in CI, never committed to tfvars.
  host = var.databricks_account_console_url
}

provider "random" {}
