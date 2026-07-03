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
  # Account-level: manages the Unity Catalog metastore and its workspace
  # assignment. Auth (ARM_CLIENT_ID / ARM_CLIENT_SECRET / ARM_TENANT_ID or
  # Azure CLI) is sourced from the environment in CI, never committed to
  # tfvars — see ../../README.md#workflow.
  alias      = "account"
  host       = var.databricks_account_console_url
  account_id = var.databricks_account_id
}

provider "databricks" {
  # Workspace-level: manages catalogs/schemas/storage credentials inside the
  # workspace created by module.databricks_workspace in this same apply.
  # Known caveat: since this provider's host is computed from a resource
  # created in the same run, the very first `terraform apply` must create
  # the workspace before any workspace-level databricks_* resource can be
  # planned — Terraform handles the ordering automatically via the implicit
  # dependency, but `-target` and `destroy` need the same care Databricks'
  # own reference examples call out for this exact pattern.
  alias = "workspace"
  host  = module.databricks_workspace.workspace_url
}

provider "random" {}
