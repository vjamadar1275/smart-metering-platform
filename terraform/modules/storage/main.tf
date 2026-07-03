locals {
  # Storage account names are globally unique across Azure, lowercase
  # alphanumeric only, 3-24 chars — derive a short deterministic name rather
  # than requiring every caller to hand-pick one.
  account_name = coalesce(
    var.account_name_override,
    "stsmtr${var.environment}${substr(md5("${var.environment}-${var.region}"), 0, 8)}"
  )
}

resource "azurerm_storage_account" "this" {
  name                = local.account_name
  resource_group_name = var.resource_group_name
  location            = var.region

  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = var.account_replication_type
  is_hns_enabled           = true # ADLS Gen2 hierarchical namespace

  min_tls_version                  = "TLS1_2"
  shared_access_key_enabled        = false # storage_use_azuread = true at provider level; no shared-key auth
  public_network_access_enabled    = var.private_endpoint_subnet_id != null ? false : true
  allow_nested_items_to_be_public  = false
  cross_tenant_replication_enabled = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  network_rules {
    default_action = var.private_endpoint_subnet_id != null ? "Deny" : "Allow"
    bypass         = ["AzureServices"]
  }

  tags = var.tags
}

resource "azurerm_storage_container" "this" {
  for_each = toset(var.containers)

  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "lifecycle" {
  storage_account_id = azurerm_storage_account.this.id

  rule {
    name    = "medallion-lifecycle"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = [for c in var.containers : "${c}/" if c != "unity-catalog-root"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = var.hot_to_cool_days
        tier_to_archive_after_days_since_modification_greater_than = var.cool_to_archive_days
      }
    }
  }
}

resource "azurerm_private_endpoint" "blob" {
  count = var.private_endpoint_subnet_id != null ? 1 : 0

  name                = "pe-${local.account_name}-blob"
  resource_group_name = var.resource_group_name
  location            = var.region
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${local.account_name}-blob"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  dynamic "private_dns_zone_group" {
    for_each = contains(keys(var.private_dns_zone_ids), "blob") ? [1] : []
    content {
      name                 = "default"
      private_dns_zone_ids = [var.private_dns_zone_ids["blob"]]
    }
  }

  tags = var.tags
}

resource "azurerm_private_endpoint" "dfs" {
  count = var.private_endpoint_subnet_id != null ? 1 : 0

  name                = "pe-${local.account_name}-dfs"
  resource_group_name = var.resource_group_name
  location            = var.region
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${local.account_name}-dfs"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["dfs"]
    is_manual_connection           = false
  }

  dynamic "private_dns_zone_group" {
    for_each = contains(keys(var.private_dns_zone_ids), "dfs") ? [1] : []
    content {
      name                 = "default"
      private_dns_zone_ids = [var.private_dns_zone_ids["dfs"]]
    }
  }

  tags = var.tags
}
