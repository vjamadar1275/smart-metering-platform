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

  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

provider "azuread" {}

provider "databricks" {
  # Account-level: manages prod's dedicated Unity Catalog metastore (not
  # shared with dev/staging, per ADR-0006) and its workspace assignment.
  alias      = "account"
  host       = var.databricks_account_console_url
  account_id = var.databricks_account_id
}

provider "databricks" {
  # Workspace-level: see the caveat comment in ../dev/providers.tf — the
  # same pattern applies here.
  alias = "workspace"
  host  = module.databricks_workspace.workspace_url
}

provider "random" {}
