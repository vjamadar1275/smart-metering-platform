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

variable "sku" {
  description = "Namespace SKU when not using a Dedicated cluster (use_dedicated_cluster = false): Basic, Standard, or Premium."
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "sku must be one of Basic, Standard, Premium."
  }
}

variable "use_dedicated_cluster" {
  description = "Provision a single-tenant Dedicated Event Hubs Cluster (per ADR-0001) instead of a shared-tenant namespace. Recommended true for staging/prod (throughput needs this ADR sized for); dev typically stays false to avoid the fixed cost of a dedicated cluster for a small representative-subset workload."
  type        = bool
  default     = false
}

variable "capacity_units" {
  description = "Throughput/capacity units. Meaning depends on tier: Standard-tier throughput units (max 40, ignored if auto_inflate is not used beyond this ceiling), or Premium-tier processing units, when use_dedicated_cluster is false. Sized from the capacity planning in docs/architecture/ARCHITECTURE.md#capacity-planning."
  type        = number
  default     = 1
}

variable "partition_count" {
  description = "Number of partitions for the meter-telemetry hub. Deliberately over-provisioned relative to current load per ADR-0001 (partition count cannot be safely decreased later)."
  type        = number
  default     = 200
}

variable "message_retention_days" {
  description = "Event retention in days. Standard/Basic tiers cap at 7; Premium/Dedicated support up to 90."
  type        = number
  default     = 7
}

variable "consumer_groups" {
  description = "List of consumer group names, e.g. [\"bronze-streaming\", \"anomaly-detection\", \"monitoring\"]. The $Default consumer group always exists and is not included here."
  type        = list(string)
  default     = ["bronze-streaming", "anomaly-detection", "monitoring"]
}

variable "enable_geo_dr" {
  description = "Whether to configure Geo-Disaster Recovery pairing to a secondary namespace (prod only). Requires Standard or higher (not Basic)."
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

variable "private_dns_zone_id" {
  description = "Resource ID of the privatelink.servicebus.windows.net Private DNS zone (from the networking module)."
  type        = string
  default     = null
}

variable "key_vault_id" {
  description = "Key Vault ID (from the key-vault module) to store the namespace's primary connection string in, for consumption by Structured Streaming jobs and the Event Hub simulator."
  type        = string
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
