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

variable "databricks_account_id" {
  description = "Databricks account ID (GUID, from the account console). Required for account-level provider operations (metastore creation/assignment)."
  type        = string
}

variable "metastore_owner_group" {
  description = "Account-level group name that owns/administers prod's dedicated Unity Catalog metastore."
  type        = string
  default     = "account-admins"
}

variable "vnet_address_space" {
  description = "CIDR address space for this environment's VNet."
  type        = list(string)
  default     = ["10.10.0.0/16"]
}

variable "subnet_cidrs" {
  description = "Per-purpose subnet CIDRs within the VNet address space."
  type        = map(string)
  default = {
    databricks_public  = "10.10.1.0/24"
    databricks_private = "10.10.2.0/24"
    private_endpoints  = "10.10.3.0/24"
    firewall           = "10.10.0.0/26"
  }
}

variable "enable_firewall" {
  description = "Whether to provision Azure Firewall for egress filtering. Always true in prod."
  type        = bool
  default     = true
}

variable "event_hub_partition_count" {
  description = "Partition count for the meter-telemetry Event Hub, per ADR-0001's over-provisioned default sized for the 10M/100M-meter capacity plan."
  type        = number
  default     = 200
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

variable "sql_warehouse_bi_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-bi — per ADR-0005, broad access for scheduled BI/Power BI refreshes."
  type        = list(string)
  default     = ["smartmeter-prod-bi-consumers"]
}

variable "sql_warehouse_adhoc_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-adhoc — per ADR-0005, all analysts."
  type        = list(string)
  default     = ["smartmeter-prod-analysts"]
}

variable "sql_warehouse_executive_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-executive — per ADR-0005, a small named group, deliberately narrower than sqlw-adhoc's."
  type        = list(string)
  default     = ["smartmeter-prod-executives"]
}
