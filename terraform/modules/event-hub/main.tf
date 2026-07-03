locals {
  is_premium_tier = var.use_dedicated_cluster || var.sku == "Premium"
}

resource "azurerm_eventhub_cluster" "this" {
  count = var.use_dedicated_cluster ? 1 : 0

  name                = "evhc-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region
  sku_name            = "Dedicated_1"
  tags                = var.tags
}

resource "azurerm_eventhub_namespace" "this" {
  name                = "evhns-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region

  sku                  = var.use_dedicated_cluster ? "Premium" : var.sku
  capacity             = var.use_dedicated_cluster ? null : var.capacity_units
  dedicated_cluster_id = var.use_dedicated_cluster ? azurerm_eventhub_cluster.this[0].id : null

  auto_inflate_enabled         = !var.use_dedicated_cluster && var.sku != "Basic"
  maximum_throughput_units     = !var.use_dedicated_cluster && var.sku != "Basic" ? 40 : null
  local_authentication_enabled = true # required for the SASL/PLAIN connection-string auth Structured Streaming's Kafka connector uses; see ADR-0009

  public_network_access_enabled = var.private_endpoint_subnet_id != null ? false : true

  network_rulesets {
    default_action                 = var.private_endpoint_subnet_id != null ? "Deny" : "Allow"
    public_network_access_enabled  = var.private_endpoint_subnet_id != null ? false : true
    trusted_service_access_enabled = true
  }

  tags = var.tags
}

resource "azurerm_eventhub" "meter_telemetry" {
  name              = "evh-meter-telemetry"
  namespace_id      = azurerm_eventhub_namespace.this.id
  partition_count   = var.partition_count
  message_retention = local.is_premium_tier ? null : var.message_retention_days

  dynamic "retention_description" {
    for_each = local.is_premium_tier ? [1] : []
    content {
      cleanup_policy          = "Delete"
      retention_time_in_hours = var.message_retention_days * 24
    }
  }

  # Event Hubs Capture (auto-archive to ADLS) is intentionally not enabled:
  # Bronze already durably lands every event via Structured Streaming, so a
  # second raw-retention path would duplicate storage cost without adding
  # a capability the medallion architecture doesn't already provide.
}

resource "azurerm_eventhub_consumer_group" "this" {
  for_each = toset(var.consumer_groups)

  name                = each.value
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.meter_telemetry.name
  resource_group_name = var.resource_group_name
  user_metadata       = "Managed by Terraform — smart-metering-platform."
}

resource "azurerm_eventhub_namespace_schema_group" "this" {
  name                 = "sg-meter-telemetry"
  namespace_id         = azurerm_eventhub_namespace.this.id
  schema_compatibility = "Backward"
  schema_type          = "Avro"

  # Individual schema *versions* (schemas/avro/meter_telemetry.avsc in this
  # repo) are registered into this group via the Schema Registry API/SDK as
  # part of pipeline deployment, not by Terraform — Terraform's provider
  # manages the registry container, not per-version schema documents, the
  # same way it wouldn't manage individual Kafka topic message contents.
}

resource "azurerm_eventhub_namespace_disaster_recovery_config" "this" {
  count = var.enable_geo_dr ? 1 : 0

  name                 = "geodr-smartmeter-${var.environment}"
  namespace_name       = azurerm_eventhub_namespace.this.name
  resource_group_name  = var.resource_group_name
  partner_namespace_id = var.geo_dr_secondary_namespace_id
}

resource "azurerm_private_endpoint" "this" {
  count = var.private_endpoint_subnet_id != null ? 1 : 0

  name                = "pe-${azurerm_eventhub_namespace.this.name}"
  resource_group_name = var.resource_group_name
  location            = var.region
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${azurerm_eventhub_namespace.this.name}"
    private_connection_resource_id = azurerm_eventhub_namespace.this.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }

  dynamic "private_dns_zone_group" {
    for_each = var.private_dns_zone_id != null ? [1] : []
    content {
      name                 = "default"
      private_dns_zone_ids = [var.private_dns_zone_id]
    }
  }

  tags = var.tags
}

resource "azurerm_key_vault_secret" "connection_string" {
  name         = "evhns-${var.environment}-connection-string"
  key_vault_id = var.key_vault_id
  value        = azurerm_eventhub_namespace.this.default_primary_connection_string
  content_type = "text/plain"

  tags = var.tags
}
