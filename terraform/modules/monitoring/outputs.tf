output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.id
}

output "alert_action_group_id" {
  description = "Resource ID of the shared Azure Monitor action group used by alert rules across the platform."
  value       = azurerm_monitor_action_group.this.id
}
