variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the Event Hubs namespace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the Event Hubs namespace is created in."
  type        = string
}

variable "capacity_units" {
  description = "Number of Capacity Units for the Dedicated-tier namespace. Sized from the capacity planning in docs/architecture/ARCHITECTURE.md#capacity-planning."
  type        = number
  default     = 1
}

variable "partition_count" {
  description = "Number of partitions for the meter-telemetry hub. Deliberately over-provisioned relative to current load per ADR-0001 (partition count cannot be safely decreased later)."
  type        = number
  default     = 200
}

variable "message_retention_days" {
  description = "Event retention in days (Dedicated tier supports up to 90)."
  type        = number
  default     = 7
}

variable "consumer_groups" {
  description = "List of consumer group names, e.g. [\"bronze-streaming\", \"anomaly-detection\", \"monitoring\"]."
  type        = list(string)
}

variable "enable_geo_dr" {
  description = "Whether to configure Geo-Disaster Recovery pairing to a secondary namespace (prod only)."
  type        = bool
  default     = false
}

variable "geo_dr_secondary_namespace_id" {
  description = "Resource ID of the secondary-region Event Hubs namespace to pair with, if enable_geo_dr is true."
  type        = string
  default     = null
}

variable "private_endpoint_subnet_id" {
  description = "Subnet ID for the namespace's Private Endpoint (from the networking module)."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
