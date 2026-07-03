locals {
  standard_tags = merge(
    {
      environment         = var.environment
      owner               = var.owner
      cost_center         = var.cost_center
      managed_by          = "terraform"
      project             = "smart-metering-platform"
      data_classification = "internal"
    },
    var.tags
  )

  name_prefix = "smartmeter-${var.environment}"
}

# Phase 2 scope: see ../dev/main.tf header comment. Staging attaches to dev's
# Unity Catalog metastore rather than creating its own, per ADR-0006.

data "azurerm_client_config" "current" {}

data "terraform_remote_state" "dev" {
  backend = "azurerm"

  config = {
    resource_group_name  = var.dev_state.resource_group_name
    storage_account_name = var.dev_state.storage_account_name
    container_name       = var.dev_state.container_name
    key                  = var.dev_state.key
    use_azuread_auth     = true
  }
}

resource "azurerm_resource_group" "network" {
  name     = "rg-${local.name_prefix}-network"
  location = var.primary_region
  tags     = local.standard_tags
}

resource "azurerm_resource_group" "data" {
  name     = "rg-${local.name_prefix}-data"
  location = var.primary_region
  tags     = local.standard_tags
}

resource "azurerm_resource_group" "databricks" {
  name     = "rg-${local.name_prefix}-databricks"
  location = var.primary_region
  tags     = local.standard_tags
}

resource "azurerm_resource_group" "monitoring" {
  name     = "rg-${local.name_prefix}-monitoring"
  location = var.primary_region
  tags     = local.standard_tags
}

module "networking" {
  source = "../../modules/networking"

  environment         = var.environment
  region              = var.primary_region
  resource_group_name = azurerm_resource_group.network.name
  vnet_address_space  = var.vnet_address_space
  subnet_cidrs        = var.subnet_cidrs
  enable_firewall     = var.enable_firewall
  tags                = local.standard_tags
}

module "key_vault" {
  source = "../../modules/key-vault"

  environment                = var.environment
  region                     = var.primary_region
  resource_group_name        = azurerm_resource_group.data.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "premium"
  purge_protection_enabled   = true
  private_endpoint_subnet_id = module.networking.subnet_ids["private_endpoints"]
  private_dns_zone_id        = module.networking.private_dns_zone_ids["privatelink.vaultcore.azure.net"]
  authorized_principals = {
    deployer = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Key Vault Administrator"
    }
  }
  tags = local.standard_tags
}

module "managed_identity" {
  source = "../../modules/managed-identity"

  environment         = var.environment
  region              = var.primary_region
  resource_group_name = azurerm_resource_group.databricks.name
  identities          = ["bronze-pipeline", "silver-pipeline", "gold-pipeline", "model-serving", "cicd-deploy"]
  tags                = local.standard_tags
}

module "storage" {
  source = "../../modules/storage"

  environment                = var.environment
  region                     = var.primary_region
  resource_group_name        = azurerm_resource_group.data.name
  account_replication_type   = "ZRS"
  containers                 = ["bronze", "silver", "gold", "checkpoints", "unity-catalog-root"]
  private_endpoint_subnet_id = module.networking.subnet_ids["private_endpoints"]
  private_dns_zone_ids = {
    blob = module.networking.private_dns_zone_ids["privatelink.blob.core.windows.net"]
    dfs  = module.networking.private_dns_zone_ids["privatelink.dfs.core.windows.net"]
  }
  tags = local.standard_tags
}

module "databricks_workspace" {
  source = "../../modules/databricks-workspace"

  environment                       = var.environment
  region                            = var.primary_region
  resource_group_name               = azurerm_resource_group.databricks.name
  sku                               = "premium"
  vnet_id                           = module.networking.vnet_id
  public_subnet_name                = module.networking.subnet_names["databricks_public"]
  private_subnet_name               = module.networking.subnet_names["databricks_private"]
  public_subnet_nsg_association_id  = module.networking.nsg_association_ids["databricks_public"]
  private_subnet_nsg_association_id = module.networking.nsg_association_ids["databricks_private"]
  no_public_ip                      = true
  managed_resource_group_name       = "rg-${local.name_prefix}-databricks-managed"
  tags                              = local.standard_tags
}

locals {
  unity_catalog_container       = "unity-catalog-root"
  catalog_name                  = "smartmeter_${var.environment}"
  catalog_external_location_url = "abfss://${local.unity_catalog_container}@${module.storage.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/"
}

module "unity_catalog" {
  source = "../../modules/unity-catalog"

  environment           = var.environment
  region                = var.primary_region
  resource_group_name   = azurerm_resource_group.databricks.name
  metastore_name        = "metastore-smartmeter-${var.primary_region}" # unused: create_metastore = false
  create_metastore      = false                                        # staging attaches to dev's metastore, per ADR-0006
  existing_metastore_id = data.terraform_remote_state.dev.outputs.metastore_id
  workspace_id_numeric  = module.databricks_workspace.workspace_id_numeric
  storage_account_id    = module.storage.storage_account_id
  catalog_name          = local.catalog_name
  external_location_url = local.catalog_external_location_url
  tags                  = local.standard_tags

  providers = {
    databricks.account   = databricks.account
    databricks.workspace = databricks.workspace
  }
}
