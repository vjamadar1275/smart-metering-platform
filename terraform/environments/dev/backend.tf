# Remote state backend — see ../../README.md#state-backend for the bootstrap process.
# The storage account/container referenced here are provisioned out-of-band, before
# `terraform init` is first run against this environment.
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-smartmeter-tfstate"
    storage_account_name = "stsmtrtfstateeus2"
    container_name       = "tfstate"
    key                  = "dev/smartmetering.tfstate"
    use_azuread_auth     = true
  }
}
