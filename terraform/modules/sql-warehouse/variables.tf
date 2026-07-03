variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "warehouse_name" {
  description = "Name of the SQL Warehouse, e.g. sqlw-bi, sqlw-adhoc, sqlw-executive."
  type        = string
}

variable "warehouse_purpose" {
  description = "Workload class this warehouse is isolated for, per ADR-0005."
  type        = string

  validation {
    condition     = contains(["bi", "adhoc", "executive"], var.warehouse_purpose)
    error_message = "warehouse_purpose must be one of bi, adhoc, executive."
  }
}

variable "cluster_size" {
  description = "SQL Warehouse cluster size (e.g. 2X-Small, Small, Medium)."
  type        = string
  default     = "Small"
}

variable "min_clusters" {
  description = "Minimum number of clusters for multi-cluster autoscaling."
  type        = number
  default     = 1
}

variable "max_clusters" {
  description = "Maximum number of clusters for multi-cluster autoscaling."
  type        = number
  default     = 4
}

variable "auto_stop_minutes" {
  description = "Idle minutes before the warehouse auto-stops. Serverless warehouses stop quickly; kept low for bi/executive, slightly higher for adhoc to avoid cold-start thrash during analyst working sessions."
  type        = number
  default     = 10
}

variable "enable_serverless" {
  description = "Use Serverless SQL compute (recommended for all three warehouse types per ADR-0007)."
  type        = bool
  default     = true
}

variable "enable_photon" {
  description = "Enable Photon vectorized execution."
  type        = bool
  default     = true
}

variable "authorized_group_names" {
  description = "Entra security group names granted CAN_USE on this warehouse (scopes access per warehouse, e.g. a small named group for sqlw-executive vs. all analysts for sqlw-adhoc)."
  type        = list(string)
}

variable "tags" {
  description = "Tags applied to the warehouse resource."
  type        = map(string)
  default     = {}
}
