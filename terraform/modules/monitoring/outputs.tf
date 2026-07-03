output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = null # populated in Phase 8
}

output "alert_action_group_id" {
  description = "Resource ID of the shared Azure Monitor action group used by alert rules across the platform."
  value       = null # populated in Phase 8
}
