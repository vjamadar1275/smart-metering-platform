output "namespace_id" {
  description = "Resource ID of the Event Hubs namespace."
  value       = null # populated in Phase 3
}

output "event_hub_id" {
  description = "Resource ID of the meter-telemetry Event Hub."
  value       = null # populated in Phase 3
}

output "geo_dr_alias_name" {
  description = "Geo-DR alias name consumers should connect to (stable across failover)."
  value       = null # populated in Phase 3
}

output "connection_string_secret_name" {
  description = "Name of the Key Vault secret holding the namespace connection string (value itself is never a Terraform output)."
  value       = null # populated in Phase 3
}
