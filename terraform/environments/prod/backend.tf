# Remote state backend — see ../../README.md#state-backend for the bootstrap process.
terraform {
  backend "azurerm" {
    resource_group_name = "rg-smartmeter-tfstate"
    storage_account_name = "stsmtrtfstateeus2"
    container_name        = "tfstate"
    key                    = "prod/smartmetering.tfstate"
    use_azuread_auth       = true
  }
}
