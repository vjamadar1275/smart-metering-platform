locals {
  standard_tags = merge(
    {
      environment         = var.environment
      owner               = var.owner
      cost_center         = var.cost_center
      managed_by          = "terraform"
      project             = "smart-metering-platform"
      data_classification = "restricted" # prod carries regulated/PII utility customer data
    },
    var.tags
  )

  name_prefix    = "smartmeter-${var.environment}"
  dr_name_prefix = "smartmeter-${var.environment}-dr"
}

# Phase 2 scope: see ../dev/main.tf header comment. Production additionally
# provisions secondary-region resource groups for the warm-standby DR strategy
# documented in docs/architecture/diagrams/disaster-recovery-diagram.md; the
# resources within them (Event Hubs Geo-DR pairing, ADLS GZRS replica, standby
# Databricks workspace) are wired in Phase 3/8 alongside the modules that own
# them (event-hub, monitoring) — this phase provisions the DR resource groups
# only, so they exist as a stable target for those later modules.

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

resource "azurerm_resource_group" "dr_data" {
  count    = var.enable_dr_region ? 1 : 0
  name     = "rg-${local.dr_name_prefix}-data"
  location = var.secondary_region
  tags     = merge(local.standard_tags, { role = "disaster-recovery" })
}

resource "azurerm_resource_group" "dr_databricks" {
  count    = var.enable_dr_region ? 1 : 0
  name     = "rg-${local.dr_name_prefix}-databricks"
  location = var.secondary_region
  tags     = merge(local.standard_tags, { role = "disaster-recovery" })
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
  account_replication_type   = "GZRS" # geo-zone-redundant: backs the warm-standby DR strategy
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
  use_dedicated_cluster      = true # per ADR-0001: full fleet throughput requires Dedicated tier
  partition_count            = var.event_hub_partition_count
  message_retention_days     = 14
  private_endpoint_subnet_id = module.networking.subnet_ids["private_endpoints"]
  private_dns_zone_id        = module.networking.private_dns_zone_ids["privatelink.servicebus.windows.net"]
  key_vault_id               = module.key_vault.key_vault_id
  # Geo-DR pairing to the secondary region (docs/architecture/diagrams/
  # disaster-recovery-diagram.md) is not wired yet: it requires a bare
  # secondary-region namespace as the Geo-DR replication target, which is
  # provisioned alongside the rest of the DR failover path in Phase 8, not
  # created piecemeal here.
  enable_geo_dr = false
  tags          = local.standard_tags
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

# See ../dev/main.tf's identical block for the full explanation.
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
  metastore_name             = "metastore-smartmeter-${var.environment}-${var.primary_region}" # prod: dedicated metastore, not shared, per ADR-0006
  create_metastore           = true
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

# --- SQL Warehouses: workload-isolated per ADR-0005 (Phase 6) ---
# prod sized for headroom toward the design-target device count, per
# meter_device_count_target's own rationale above; revisit once Phase 8
# Lakehouse Monitoring/query history gives real usage data (ADR-0005's
# consequence).

module "sql_warehouse_bi" {
  source = "../../modules/sql-warehouse"

  environment            = var.environment
  warehouse_name         = "sqlw-bi"
  warehouse_purpose      = "bi"
  cluster_size           = "Small"
  min_clusters           = 2
  max_clusters           = 8
  auto_stop_minutes      = 10
  authorized_group_names = var.sql_warehouse_bi_group_names
  tags                   = local.standard_tags

  providers = {
    databricks.workspace = databricks.workspace
  }
}

module "sql_warehouse_adhoc" {
  source = "../../modules/sql-warehouse"

  environment            = var.environment
  warehouse_name         = "sqlw-adhoc"
  warehouse_purpose      = "adhoc"
  cluster_size           = "Medium"
  min_clusters           = 2
  max_clusters           = 6
  auto_stop_minutes      = 20
  authorized_group_names = var.sql_warehouse_adhoc_group_names
  tags                   = local.standard_tags

  providers = {
    databricks.workspace = databricks.workspace
  }
}

module "sql_warehouse_executive" {
  source = "../../modules/sql-warehouse"

  environment            = var.environment
  warehouse_name         = "sqlw-executive"
  warehouse_purpose      = "executive"
  cluster_size           = "Small"
  min_clusters           = 2
  max_clusters           = 4
  auto_stop_minutes      = 10
  authorized_group_names = var.sql_warehouse_executive_group_names
  tags                   = local.standard_tags

  providers = {
    databricks.workspace = databricks.workspace
  }
}
