variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the workspace is created in."
  type        = string
}

variable "sku" {
  description = "Databricks workspace SKU."
  type        = string
  default     = "premium"

  validation {
    condition     = contains(["standard", "premium", "trial"], var.sku)
    error_message = "sku must be one of standard, premium, trial. Premium is required for Unity Catalog + SCC + cluster policies."
  }
}

variable "vnet_id" {
  description = "VNet ID to inject the workspace into (from the networking module)."
  type        = string
}

variable "public_subnet_name" {
  description = "Name of the 'public' (host) subnet for VNet injection."
  type        = string
}

variable "private_subnet_name" {
  description = "Name of the 'private' (container) subnet for VNet injection."
  type        = string
}

variable "no_public_ip" {
  description = "Disable public IPs on cluster nodes (Secure Cluster Connectivity). Must be true for prod."
  type        = bool
  default     = true
}

variable "managed_resource_group_name" {
  description = "Name of the Databricks-managed resource group (created automatically by the workspace resource)."
  type        = string
}

variable "tags" {
  description = "Tags applied to the workspace resource."
  type        = map(string)
  default     = {}
}
