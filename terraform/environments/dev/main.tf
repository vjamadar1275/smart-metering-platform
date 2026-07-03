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
# Phase 1 scope: this file establishes provider/backend/variable/tag
# conventions only. Module calls (networking, storage, key-vault,
# managed-identity, event-hub, databricks-workspace, unity-catalog,
# sql-warehouse, monitoring) are added in Phase 2, in dependency order:
#
#   module "networking"          -> module "key_vault" / "managed_identity"
#   -> module "storage" -> module "event_hub"
#   -> module "databricks_workspace" -> module "unity_catalog"
#   -> module "sql_warehouse" -> module "monitoring"
#
# Each module's interface (variables.tf / outputs.tf) is already defined
# under ../../modules/*/ so Phase 2 is a matter of wiring, not design.
# ---------------------------------------------------------------------------

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
