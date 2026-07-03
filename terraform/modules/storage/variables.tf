variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the storage account."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the storage account is created in."
  type        = string
}

variable "account_replication_type" {
  description = "Storage replication type. Use GZRS for prod (geo-zone-redundant, backs the DR strategy), ZRS acceptable for dev/staging."
  type        = string
  default     = "ZRS"

  validation {
    condition     = contains(["ZRS", "GZRS", "LRS", "GRS"], var.account_replication_type)
    error_message = "account_replication_type must be one of ZRS, GZRS, LRS, GRS."
  }
}

variable "containers" {
  description = "List of container names to create, e.g. [\"bronze\", \"silver\", \"gold\", \"checkpoints\", \"unity-catalog-root\"]."
  type        = list(string)
}

variable "hot_to_cool_days" {
  description = "Days after last modification before a blob transitions Hot -> Cool, per the 90-day Bronze retention policy."
  type        = number
  default     = 90
}

variable "cool_to_archive_days" {
  description = "Days after last modification before a blob transitions Cool -> Archive."
  type        = number
  default     = 365
}

variable "private_endpoint_subnet_id" {
  description = "Subnet ID for the storage account's Private Endpoint (from the networking module)."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
