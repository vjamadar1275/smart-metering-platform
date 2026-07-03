variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the metastore (metastores are regional; dev/staging share one, prod has a dedicated one per ADR-0006)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the Azure Databricks Access Connector is created in."
  type        = string
}

variable "metastore_name" {
  description = "Name of the Unity Catalog metastore. Only used if create_metastore is true."
  type        = string
}

variable "create_metastore" {
  description = "Whether this environment owns metastore creation (true for the first environment provisioned per region-tier; false for environments attaching to an already-created shared metastore, e.g. staging attaching to dev's metastore)."
  type        = bool
  default     = false
}

variable "existing_metastore_id" {
  description = "Metastore ID to attach to when create_metastore is false (e.g. staging passes dev's metastore_id output, read via a terraform_remote_state data source at the environment root)."
  type        = string
  default     = null
}

variable "metastore_storage_root_url" {
  description = "abfss:// URL of the ADLS container used as the metastore's default managed storage root. Only used if create_metastore is true."
  type        = string
  default     = null
}

variable "metastore_owner" {
  description = "Account-level group name that owns/administers the metastore. Only used if create_metastore is true."
  type        = string
  default     = "account-admins"
}

variable "workspace_id_numeric" {
  description = "Numeric ID of the Databricks workspace to bind to this metastore."
  type        = string
}

variable "storage_account_id" {
  description = "Resource ID of the ADLS Gen2 storage account (from the storage module) that the Access Connector is granted Storage Blob Data Contributor on."
  type        = string
}

variable "catalog_name" {
  description = "Name of this environment's catalog, e.g. smartmeter_dev / smartmeter_staging / smartmeter_prod."
  type        = string
}

variable "schemas" {
  description = "Schemas to create within the catalog."
  type        = list(string)
  default     = ["bronze", "silver", "gold", "ml", "quarantine", "reference"]
}

variable "external_location_url" {
  description = "abfss:// URL for this catalog's external location (may differ from the metastore root, e.g. a dedicated storage account per environment)."
  type        = string
}

variable "tags" {
  description = "Tags applied via Unity Catalog resource properties (catalog-level)."
  type        = map(string)
  default     = {}
}
