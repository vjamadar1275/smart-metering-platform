variable "subscription_id" {
  description = "Azure subscription ID that hosts the prod environment resources."
  type        = string
}

variable "environment" {
  description = "Environment short name, used in resource naming and tagging."
  type        = string
  default     = "prod"

  validation {
    condition     = var.environment == "prod"
    error_message = "This root module is prod-only; use environments/dev or environments/staging for other environments."
  }
}

variable "primary_region" {
  description = "Primary Azure region for this environment."
  type        = string
  default     = "eastus2"
}

variable "secondary_region" {
  description = "Paired Azure region used for warm-standby disaster recovery (see docs/architecture/diagrams/disaster-recovery-diagram.md)."
  type        = string
  default     = "centralus"
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
  default     = 10000000 # current production scale; modules are sized with headroom toward the 100,000,000 design target
}

variable "enable_dr_region" {
  description = "Whether to provision the secondary-region warm-standby resource groups. Kept as a flag so DR infrastructure can be toggled independently of primary-region changes during initial rollout."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional free-form tags merged with the standard tag set."
  type        = map(string)
  default     = {}
}
