variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the Log Analytics workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the monitoring resources are created in."
  type        = string
}

variable "log_analytics_sku" {
  description = "Log Analytics Workspace pricing tier."
  type        = string
  default     = "PerGB2018"
}

variable "retention_days" {
  description = "Log retention in days. Longer in prod for audit/compliance (see security-diagram.md)."
  type        = number
  default     = 90
}

variable "diagnostic_target_resource_ids" {
  description = "Resource IDs to attach diagnostic settings to (Databricks workspace, Event Hubs namespace, storage account, Key Vault, etc.)."
  type        = list(string)
  default     = []
}

variable "alert_action_group_email_receivers" {
  description = "Map of receiver name to email address for the shared alert action group (pipeline failures, streaming lag, cost anomalies, security alerts)."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
