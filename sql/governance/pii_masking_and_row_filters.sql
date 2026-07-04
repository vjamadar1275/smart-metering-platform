-- Unity Catalog column masking and row-level security (Phase 8).
--
-- UNLIKE sql/ddl/*.sql (documentation-only reference for Lakeflow-managed
-- tables), this script is meant to actually be run once per environment
-- by a Unity Catalog admin, against the environment's catalog — these are
-- governance objects (masking/row-filter functions + ALTER TABLE grants),
-- not table schemas a pipeline manages. Run via a SQL Warehouse
-- (sqlw-adhoc or a dedicated admin warehouse), not as part of any
-- Lakeflow pipeline or Databricks Job.
--
-- Group names below (smartmeter-pii-readers, smartmeter-executives,
-- smartmeter-admins, smartmeter-analysts-<zone>) are illustrative Entra ID
-- / account-console group names an admin creates per environment — adjust
-- to match your actual provisioned groups (see
-- terraform/environments/<env>/variables.tf's sql_warehouse_*_group_names
-- for the analogous SQL Warehouse access groups this reuses the naming
-- convention from). The catalog itself is already the environment
-- boundary (ADR-0006), so these function bodies don't need an env suffix
-- baked in — the same function definition is applied fresh into each
-- environment's catalog.

USE CATALOG IDENTIFIER(current_catalog());

-- --- Column masking: reference.dim_customer PII (account_name, service_address) ---
-- Per security-diagram.md's Data Layer: "Column Masking — PII: customer
-- name, address, account no." Full value only for a small named group
-- with a legitimate need (billing, customer support); everyone else
-- (including sqlw-adhoc's broad analyst group) sees a redacted placeholder.

CREATE OR REPLACE FUNCTION reference.mask_pii_string(input STRING)
RETURNS STRING
COMMENT 'Column mask: returns the real value only for smartmeter-pii-readers members, else a fixed redaction placeholder. See ADR set / security-diagram.md.'
RETURN CASE
    WHEN is_account_group_member('smartmeter-pii-readers') THEN input
    ELSE '**REDACTED**'
END;

ALTER TABLE reference.dim_customer ALTER COLUMN account_name SET MASK reference.mask_pii_string;
ALTER TABLE reference.dim_customer ALTER COLUMN service_address SET MASK reference.mask_pii_string;

-- --- Row-level security: DMA/zone scoping on silver.meter_readings ---
-- Per security-diagram.md's Data Layer: "Row-Level Security — row filters,
-- e.g. by DMA/region." A regional analyst (group name
-- smartmeter-analysts-<zone>, e.g. smartmeter-analysts-north) sees only
-- readings from DMAs in their zone; admins/executives see every row.
-- Joins to reference.dim_dma (current version) to resolve a reading's
-- dma_id to its zone at query time.

CREATE OR REPLACE FUNCTION reference.dma_zone_row_filter(dma_id STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: true if the caller may see rows for this dma_id. Full access for smartmeter-admins/smartmeter-executives; regional analysts (smartmeter-analysts-<zone>) are scoped to their own zone via reference.dim_dma. See ADR set / security-diagram.md.'
RETURN
    is_account_group_member('smartmeter-admins')
    OR is_account_group_member('smartmeter-executives')
    OR EXISTS (
        SELECT 1
        FROM reference.dim_dma d
        WHERE d.dma_id = dma_zone_row_filter.dma_id
          AND is_account_group_member(concat('smartmeter-analysts-', lower(d.zone)))
    );

ALTER TABLE silver.meter_readings SET ROW FILTER reference.dma_zone_row_filter ON (dma_id);
ALTER TABLE gold.dma_analytics SET ROW FILTER reference.dma_zone_row_filter ON (dma_id);

-- --- Baseline schema grants (illustrative — adjust group names as above) ---
-- Least-privilege by construction, per ADR-0006's schema-per-domain
-- strategy: broad read on Gold/reference (the intended consumer-facing
-- surface), narrow/no access to bronze/silver/quarantine/ml by default.

GRANT USE CATALOG ON CATALOG IDENTIFIER(current_catalog()) TO `smartmeter-analysts`;
GRANT USE SCHEMA ON SCHEMA gold TO `smartmeter-analysts`;
GRANT USE SCHEMA ON SCHEMA reference TO `smartmeter-analysts`;
GRANT SELECT ON SCHEMA gold TO `smartmeter-analysts`;
GRANT SELECT ON SCHEMA reference TO `smartmeter-analysts`;

GRANT USE SCHEMA ON SCHEMA silver TO `smartmeter-admins`;
GRANT SELECT ON SCHEMA silver TO `smartmeter-admins`;
GRANT USE SCHEMA ON SCHEMA quarantine TO `smartmeter-admins`;
GRANT SELECT ON SCHEMA quarantine TO `smartmeter-admins`;
GRANT USE SCHEMA ON SCHEMA bronze TO `smartmeter-admins`;
GRANT SELECT ON SCHEMA bronze TO `smartmeter-admins`;
GRANT USE SCHEMA ON SCHEMA ml TO `smartmeter-admins`;
GRANT SELECT ON SCHEMA ml TO `smartmeter-admins`;
