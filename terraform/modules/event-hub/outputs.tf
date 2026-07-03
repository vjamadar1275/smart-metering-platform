output "namespace_id" {
  description = "Resource ID of the Event Hubs namespace."
  value       = azurerm_eventhub_namespace.this.id
}

output "namespace_name" {
  description = "Name of the Event Hubs namespace (the hostname is \"<name>.servicebus.windows.net\", used as the Kafka bootstrap server by Structured Streaming)."
  value       = azurerm_eventhub_namespace.this.name
}

output "event_hub_id" {
  description = "Resource ID of the meter-telemetry Event Hub."
  value       = azurerm_eventhub.meter_telemetry.id
}

output "event_hub_name" {
  description = "Name of the meter-telemetry Event Hub (the Kafka topic name)."
  value       = azurerm_eventhub.meter_telemetry.name
}

output "geo_dr_alias_name" {
  description = "Geo-DR alias name consumers should connect to (stable across failover)."
  value       = var.enable_geo_dr ? azurerm_eventhub_namespace_disaster_recovery_config.this[0].name : null
}

output "connection_string_secret_name" {
  description = "Name of the Key Vault secret holding the namespace connection string (value itself is never a Terraform output)."
  value       = azurerm_key_vault_secret.connection_string.name
}

output "schema_group_name" {
  description = "Name of the Event Hubs Schema Registry group meter-telemetry schemas are registered into."
  value       = azurerm_eventhub_namespace_schema_group.this.name
}
