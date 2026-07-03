variable "subscription_id" {
  description = "Azure subscription ID that hosts the staging environment resources."
  type        = string
}

variable "environment" {
  description = "Environment short name, used in resource naming and tagging."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "This root module is staging-only; use environments/dev or environments/prod for other environments."
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
  description = "Databricks account ID (GUID, from the account console). Required for account-level provider operations (metastore assignment)."
  type        = string
}

variable "vnet_address_space" {
  description = "CIDR address space for this environment's VNet."
  type        = list(string)
  default     = ["10.30.0.0/16"]
}

variable "subnet_cidrs" {
  description = "Per-purpose subnet CIDRs within the VNet address space."
  type        = map(string)
  default = {
    databricks_public  = "10.30.1.0/24"
    databricks_private = "10.30.2.0/24"
    private_endpoints  = "10.30.3.0/24"
    firewall           = "10.30.0.0/26"
  }
}

variable "enable_firewall" {
  description = "Whether to provision Azure Firewall for egress filtering. Staging defaults to true — it is meant to be production-shaped so egress-filtering issues surface before prod, per README.md's delivery-phase intent."
  type        = bool
  default     = true
}

variable "event_hub_partition_count" {
  description = "Partition count for the meter-telemetry Event Hub. Matches ADR-0001's over-provisioned default (200) since staging is meant to validate performance at close to production scale."
  type        = number
  default     = 200
}

variable "dev_state" {
  description = "Backend coordinates for the dev environment's Terraform state, read via terraform_remote_state to attach staging to the same shared Unity Catalog metastore dev owns, per ADR-0006."
  type = object({
    resource_group_name  = string
    storage_account_name = string
    container_name       = string
    key                  = string
  })
  default = {
    resource_group_name  = "rg-smartmeter-tfstate"
    storage_account_name = "stsmtrtfstateeus2"
    container_name       = "tfstate"
    key                  = "dev/smartmetering.tfstate"
  }
}

variable "meter_device_count_target" {
  description = "Design-target device count this environment's sizing should accommodate (informational; drives module sizing inputs added in Phase 2)."
  type        = number
  default     = 10000000 # staging is sized close to current production scale to validate performance before prod release
}

variable "tags" {
  description = "Additional free-form tags merged with the standard tag set."
  type        = map(string)
  default     = {}
}

variable "sql_warehouse_bi_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-bi — per ADR-0005, broad access for scheduled BI/Power BI refreshes."
  type        = list(string)
  default     = ["smartmeter-staging-bi-consumers"]
}

variable "sql_warehouse_adhoc_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-adhoc — per ADR-0005, all analysts."
  type        = list(string)
  default     = ["smartmeter-staging-analysts"]
}

variable "sql_warehouse_executive_group_names" {
  description = "Entra ID / account-console group names granted CAN_USE on sqlw-executive — per ADR-0005, a small named group, deliberately narrower than sqlw-adhoc's."
  type        = list(string)
  default     = ["smartmeter-staging-executives"]
}
