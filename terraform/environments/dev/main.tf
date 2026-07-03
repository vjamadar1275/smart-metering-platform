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

# ---------------------------------------------------------------------------
# Phase 2 scope: networking, key-vault, managed-identity, storage,
# databricks-workspace, unity-catalog. Event Hub (Phase 3), SQL Warehouses
# (Phase 6), and full Monitoring (Phase 8) are wired in their own phases.
# ---------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

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
  sku_name                   = "standard" # dev: Premium/HSM reserved for staging+prod
  purge_protection_enabled   = false      # dev: allow fast teardown/recreation
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

module "event_hub" {
  source = "../../modules/event-hub"

  environment                = var.environment
  region                     = var.primary_region
  resource_group_name        = azurerm_resource_group.data.name
  sku                        = "Standard"
  use_dedicated_cluster      = false # dev: functional-testing subset, not full ADR-0001 throughput scale
  capacity_units             = 2
  partition_count            = var.event_hub_partition_count
  message_retention_days     = 7
  private_endpoint_subnet_id = module.networking.subnet_ids["private_endpoints"]
  private_dns_zone_id        = module.networking.private_dns_zone_ids["privatelink.servicebus.windows.net"]
  key_vault_id               = module.key_vault.key_vault_id
  tags                       = local.standard_tags
}

module "databricks_workspace" {
  source = "../../modules/databricks-workspace"

  environment                       = var.environment
  region                            = var.primary_region
  resource_group_name               = azurerm_resource_group.databricks.name
  sku                               = "premium" # required for Unity Catalog + SCC + cluster policies
  vnet_id                           = module.networking.vnet_id
  public_subnet_name                = module.networking.subnet_names["databricks_public"]
  private_subnet_name               = module.networking.subnet_names["databricks_private"]
  public_subnet_nsg_association_id  = module.networking.nsg_association_ids["databricks_public"]
  private_subnet_nsg_association_id = module.networking.nsg_association_ids["databricks_private"]
  no_public_ip                      = true
  managed_resource_group_name       = "rg-${local.name_prefix}-databricks-managed"
  tags                              = local.standard_tags
}

# The well-known, first-party "AzureDatabricks" Enterprise Application that
# every Azure AD tenant has once Databricks is used against it — this is the
# identity a Key Vault-backed Databricks secret scope authenticates as, and
# it needs Key Vault read access independent of any workload's own managed
# identity (see terraform/modules/unity-catalog for the *workload* access
# pattern, which is separate).
data "azuread_service_principal" "azure_databricks" {
  client_id = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"
}

resource "azurerm_role_assignment" "databricks_keyvault_secrets" {
  scope                = module.key_vault.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = data.azuread_service_principal.azure_databricks.object_id
}

resource "databricks_secret_scope" "smartmeter" {
  provider = databricks.workspace

  name = "smartmeter-${var.environment}-secrets"

  keyvault_metadata {
    resource_id = module.key_vault.key_vault_id
    dns_name    = module.key_vault.vault_uri
  }

  depends_on = [azurerm_role_assignment.databricks_keyvault_secrets]
}

locals {
  unity_catalog_container       = "unity-catalog-root"
  metastore_storage_root_url    = "abfss://${local.unity_catalog_container}@${module.storage.storage_account_name}.dfs.core.windows.net/"
  catalog_name                  = "smartmeter_${var.environment}"
  catalog_external_location_url = "abfss://${local.unity_catalog_container}@${module.storage.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/"
}

module "unity_catalog" {
  source = "../../modules/unity-catalog"

  environment                = var.environment
  region                     = var.primary_region
  resource_group_name        = azurerm_resource_group.databricks.name
  metastore_name             = "metastore-smartmeter-${var.primary_region}"
  create_metastore           = true # dev owns the metastore shared with staging, per ADR-0006
  metastore_storage_root_url = local.metastore_storage_root_url
  metastore_owner            = var.metastore_owner_group
  workspace_id_numeric       = module.databricks_workspace.workspace_id_numeric
  storage_account_id         = module.storage.storage_account_id
  catalog_name               = local.catalog_name
  external_location_url      = local.catalog_external_location_url
  tags                       = local.standard_tags

  providers = {
    databricks.account   = databricks.account
    databricks.workspace = databricks.workspace
  }
}
