variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the Key Vault."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the Key Vault is created in."
  type        = string
}

variable "tenant_id" {
  description = "Microsoft Entra tenant ID."
  type        = string
}

variable "sku_name" {
  description = "Key Vault SKU. Use 'premium' in prod for HSM-backed keys."
  type        = string
  default     = "premium"

  validation {
    condition     = contains(["standard", "premium"], var.sku_name)
    error_message = "sku_name must be 'standard' or 'premium'."
  }
}

variable "purge_protection_enabled" {
  description = "Enable purge protection (required for prod to prevent permanent key/secret loss)."
  type        = bool
  default     = true
}

variable "soft_delete_retention_days" {
  description = "Soft-delete retention period in days."
  type        = number
  default     = 90
}

variable "authorized_principals" {
  description = "Map of label to { principal_id, role } granting RBAC access to the vault (Key Vault Secrets Officer / Key Vault Crypto Officer / etc). RBAC is used instead of legacy vault access policies per Microsoft's current guidance."
  type = map(object({
    principal_id = string
    role         = optional(string, "Key Vault Secrets User")
  }))
  default = {}
}

variable "private_endpoint_subnet_id" {
  description = "Subnet ID for the Key Vault's Private Endpoint (from the networking module)."
  type        = string
  default     = null
}

variable "private_dns_zone_id" {
  description = "Resource ID of the privatelink.vaultcore.azure.net Private DNS zone (from the networking module), linked to the Private Endpoint's DNS zone group."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to all resources created by this module."
  type        = map(string)
  default     = {}
}
