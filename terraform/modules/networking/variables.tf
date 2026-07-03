variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the network resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the network resources are created in."
  type        = string
}

variable "vnet_address_space" {
  description = "CIDR address space for the VNet, e.g. [\"10.10.0.0/16\"]."
  type        = list(string)
}

variable "subnet_cidrs" {
  description = "Map of subnet purpose to CIDR block, e.g. { databricks_public = \"10.10.1.0/24\", databricks_private = \"10.10.2.0/24\", private_endpoints = \"10.10.3.0/24\", firewall = \"10.10.0.0/26\" }."
  type        = map(string)
}

variable "enable_firewall" {
  description = "Whether to provision Azure Firewall for egress filtering (recommended true for staging/prod)."
  type        = bool
  default     = true
}

variable "firewall_allowed_fqdns" {
  description = "FQDN allow-list for Azure Firewall application rules (package repos, Databricks/MLflow artifact endpoints, etc.)."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
