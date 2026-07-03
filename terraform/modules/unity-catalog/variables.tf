variable "environment" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "region" {
  description = "Azure region for the metastore (metastores are regional; dev/staging share one, prod has a dedicated one per ADR-0006)."
  type        = string
}

variable "metastore_name" {
  description = "Name of the Unity Catalog metastore. Only created if create_metastore is true; otherwise this module attaches to an existing metastore by name."
  type        = string
}

variable "create_metastore" {
  description = "Whether this environment owns metastore creation (true for the first environment provisioned per region-tier; false for environments attaching to an already-created shared metastore, e.g. staging attaching to dev's metastore)."
  type        = bool
  default     = false
}

variable "metastore_storage_root_url" {
  description = "abfss:// URL of the ADLS container used as the metastore's default managed storage root."
  type        = string
}

variable "workspace_id_numeric" {
  description = "Numeric ID of the Databricks workspace to bind to this metastore."
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

variable "storage_credential_managed_identity_id" {
  description = "Resource ID of the Managed Identity Unity Catalog uses to access the external location's storage account."
  type        = string
}

variable "tags" {
  description = "Tags applied via Unity Catalog resource properties (catalog-level)."
  type        = map(string)
  default     = {}
}
