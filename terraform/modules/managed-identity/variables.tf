variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the managed identities."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the managed identities are created in."
  type        = string
}

variable "identities" {
  description = "Set of workload names to create a dedicated User-Assigned Managed Identity for, e.g. [\"bronze-pipeline\", \"silver-pipeline\", \"gold-pipeline\", \"model-serving\", \"cicd-deploy\"]."
  type        = list(string)
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
