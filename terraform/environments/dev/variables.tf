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

variable "databricks_account_id" {
  description = "Databricks account ID (GUID, from the account console). Required for account-level provider operations (metastore creation/assignment)."
  type        = string
}

variable "metastore_owner_group" {
  description = "Account-level group name that owns/administers the Unity Catalog metastore this environment creates."
  type        = string
  default     = "account-admins"
}

variable "vnet_address_space" {
  description = "CIDR address space for this environment's VNet."
  type        = list(string)
  default     = ["10.20.0.0/16"]
}

variable "subnet_cidrs" {
  description = "Per-purpose subnet CIDRs within the VNet address space."
  type        = map(string)
  default = {
    databricks_public  = "10.20.1.0/24"
    databricks_private = "10.20.2.0/24"
    private_endpoints  = "10.20.3.0/24"
    firewall           = "10.20.0.0/26"
  }
}

variable "enable_firewall" {
  description = "Whether to provision Azure Firewall for egress filtering. Dev defaults to false to avoid the fixed hourly cost of a firewall for a non-production environment; staging/prod default to true."
  type        = bool
  default     = false
}

variable "event_hub_partition_count" {
  description = "Partition count for the meter-telemetry Event Hub. Dev uses fewer partitions than staging/prod since it represents a small functional-testing device subset, not the full fleet ADR-0001 sized 200+ partitions for."
  type        = number
  default     = 32
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
