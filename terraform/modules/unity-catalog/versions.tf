terraform {
  required_providers {
    databricks = {
      source                = "databricks/databricks"
      configuration_aliases = [databricks.account, databricks.workspace]
    }
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}
