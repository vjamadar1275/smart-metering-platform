# Governance SQL

Unlike [sql/ddl/](../ddl/) (documentation-only reference for tables Lakeflow pipelines create and manage), the scripts here are **meant to be run**, once per environment, by a Unity Catalog admin — column masking functions, row-filter functions, and baseline schema grants. See each file's header comment for exactly how/where to run it and which Entra ID / account-console groups it assumes exist.

| Script | Purpose |
|---|---|
| [pii_masking_and_row_filters.sql](pii_masking_and_row_filters.sql) | Column masking on `reference.dim_customer` PII (account name, address); DMA/zone row-level security on `silver.meter_readings`/`gold.dma_analytics`; baseline least-privilege schema grants. Implements [security-diagram.md](../../docs/architecture/diagrams/security-diagram.md)'s Data Layer controls. |

Run order: apply after the environment's Terraform (catalog/schemas must exist) and after `src/jobs/seed_reference_data.py` (the tables being masked/filtered must exist). Not part of any Lakeflow pipeline or Databricks Job — these are one-time/rarely-changed governance objects, applied manually via a SQL Warehouse.
