# --- Access Connector: the identity Unity Catalog uses to reach ADLS Gen2 ---
# on this platform's behalf, per Databricks' current (non-deprecated) Azure
# storage-credential pattern — a raw user-assigned identity + federated
# credential is the legacy approach; the Access Connector is what Databricks
# and Microsoft jointly document as current.

resource "azurerm_databricks_access_connector" "this" {
  name                = "dbac-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "access_connector_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.this.identity[0].principal_id
}

# --- Metastore: created once per region-tier, attached by every environment ---
# sharing it (see ADR-0006). create_metastore is true only for the environment
# that owns creation; others pass existing_metastore_id.

resource "databricks_metastore" "this" {
  count    = var.create_metastore ? 1 : 0
  provider = databricks.account

  name          = var.metastore_name
  storage_root  = var.metastore_storage_root_url
  region        = var.region
  owner         = var.metastore_owner
  force_destroy = false
}

resource "databricks_metastore_data_access" "this" {
  count    = var.create_metastore ? 1 : 0
  provider = databricks.account

  metastore_id = databricks_metastore.this[0].id
  name         = "${var.metastore_name}-default-access"
  is_default   = true

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.this.id
  }
}

locals {
  metastore_id = var.create_metastore ? databricks_metastore.this[0].id : var.existing_metastore_id
}

resource "databricks_metastore_assignment" "this" {
  provider = databricks.account

  metastore_id         = local.metastore_id
  workspace_id         = var.workspace_id_numeric
  default_catalog_name = var.catalog_name
}

# --- Catalog / schemas: workspace-level, once the metastore is assigned ---

resource "databricks_storage_credential" "this" {
  provider = databricks.workspace

  name    = "cred-${var.catalog_name}"
  comment = "Storage credential for ${var.catalog_name}, backed by the ${azurerm_databricks_access_connector.this.name} Access Connector."

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.this.id
  }

  depends_on = [databricks_metastore_assignment.this]
}

resource "databricks_external_location" "this" {
  provider = databricks.workspace

  name            = "loc-${var.catalog_name}"
  url             = var.external_location_url
  credential_name = databricks_storage_credential.this.name
  comment         = "External location backing the ${var.catalog_name} catalog."
}

resource "databricks_catalog" "this" {
  provider = databricks.workspace

  name         = var.catalog_name
  storage_root = var.external_location_url
  comment      = "Smart Metering Platform — ${var.environment} catalog. Schemas: bronze/silver/gold/ml/quarantine/reference per ADR-0006."

  depends_on = [databricks_external_location.this]
}

resource "databricks_schema" "this" {
  for_each = toset(var.schemas)
  provider = databricks.workspace

  catalog_name = databricks_catalog.this.name
  name         = each.value
  comment      = "${each.value} layer for the Smart Metering Platform ${var.environment} catalog."
}
