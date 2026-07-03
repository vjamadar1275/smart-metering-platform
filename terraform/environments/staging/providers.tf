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
  # Account-level: manages the metastore *assignment* only — staging does not
  # own metastore creation, it attaches to dev's (see ADR-0006 and
  # data.terraform_remote_state.dev in main.tf).
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
