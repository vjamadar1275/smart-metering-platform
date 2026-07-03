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

  name_prefix           = "smartmeter-${var.environment}"
  dr_name_prefix         = "smartmeter-${var.environment}-dr"
}

# Phase 1 scope note: see ../dev/main.tf header comment. Production additionally
# provisions secondary-region resource groups for the warm-standby DR strategy
# documented in docs/architecture/diagrams/disaster-recovery-diagram.md; the
# resources within them (Event Hubs Geo-DR pairing, ADLS GZRS, standby Databricks
# workspace) are wired in Phase 2/8 alongside the rest of the infrastructure modules.

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
