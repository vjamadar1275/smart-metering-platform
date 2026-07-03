variable "subscription_id" {
  description = "Azure subscription ID that hosts the dev environment resources."
  type        = string
}

variable "environment" {
  description = "Environment short name, used in resource naming and tagging."
  type        = string
  default     = "dev"

  validation {
    condition     = var.environment == "dev"
    error_message = "This root module is dev-only; use environments/staging or environments/prod for other environments."
  }
}

variable "primary_region" {
  description = "Primary Azure region for this environment."
  type        = string
  default     = "eastus2"
}

variable "owner" {
  description = "Tag: team or individual accountable for these resources."
  type        = string
  default     = "data-platform-team"
}

variable "cost_center" {
  description = "Tag: cost center for chargeback/showback reporting."
  type        = string
}

variable "databricks_account_console_url" {
  description = "Databricks account console URL (https://accounts.azuredatabricks.net) used for account-level provider operations."
  type        = string
  default     = "https://accounts.azuredatabricks.net"
}

variable "meter_device_count_target" {
  description = "Design-target device count this environment's sizing should accommodate (informational; drives module sizing inputs added in Phase 2)."
  type        = number
  default     = 1000000 # dev is sized for a 1M-meter representative subset, not the full 10M/100M production scale
}

variable "tags" {
  description = "Additional free-form tags merged with the standard tag set."
  type        = map(string)
  default     = {}
}
