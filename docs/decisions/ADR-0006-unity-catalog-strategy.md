# ADR-0006: Catalog-per-Environment, Schema-per-Domain Unity Catalog Strategy

## Status
Accepted

## Context
Unity Catalog's three-level namespace (`catalog.schema.table`) needs a consistent strategy for separating dev/staging/prod, and for organizing the many tables this platform produces (Bronze/Silver/Gold × telemetry, DMA, customer, ML feature tables, quarantine tables) so that permissions, lineage, and data sharing remain manageable as the table count grows into the hundreds.

Options considered:

1. **Catalog-per-environment** (`smartmeter_dev`, `smartmeter_staging`, `smartmeter_prod`), **schema-per-domain** within each (`bronze`, `silver`, `gold`, `ml`, `quarantine`)
2. **Single catalog**, environment distinguished by schema prefix (`prod_gold`, `dev_gold`, ...)
3. **Catalog-per-domain** (`bronze_catalog`, `silver_catalog`, `gold_catalog`), environment distinguished by schema

## Decision
**Catalog-per-environment, schema-per-domain**: one catalog per environment (`smartmeter_dev`, `smartmeter_staging`, `smartmeter_prod`), each containing schemas `bronze`, `silver`, `gold`, `ml`, `quarantine`, `reference` (dimension/master data).

## Rationale

- **vs. single catalog with prefixed schemas**: catalogs, not schemas, are Unity Catalog's primary permission and data-sharing boundary. A `GRANT` mistake that's scoped to a catalog fails closed (wrong catalog = obviously wrong); a `GRANT` mistake scoped only by schema *name* prefix within one catalog is a much easier human error to make (e.g. a wildcard grant intended for `dev_*` schemas accidentally matching `prod_gold` if naming isn't perfectly disciplined). Catalog-level isolation makes the dev/staging/prod boundary structural rather than convention-dependent — this is Databricks' own recommended pattern for exactly this reason.
- **vs. catalog-per-domain**: organizing catalogs by medallion layer (Bronze catalog, Silver catalog, Gold catalog) would mean environment separation has to happen *within* each domain catalog via schema naming — reintroducing the same convention-dependent risk the catalog-per-environment choice is meant to avoid, just at a different level. Domain (Bronze/Silver/Gold/ml) varies far less in its access-control needs across environments than environment itself does (prod data is regulated/PII-sensitive; dev data is synthetic), so environment is the higher-priority axis to make structural.
- **Schema-per-domain within each catalog** keeps the domain organization Databricks documentation and tooling (Lakeflow, lineage graphs) already expect, and keeps `quarantine` and `reference` tables clearly separated from the core medallion flow without inventing a fourth catalog for what are support tables, not a fourth data-quality tier.

## Consequences

- Cross-environment queries (e.g. comparing staging Gold output to prod Gold output during a release validation) require fully qualified three-level names across catalogs — an accepted minor verbosity cost.
- **Metastore topology**: one Unity Catalog metastore per region, shared by dev and staging workspaces, with a separate dedicated metastore for prod (see [deployment-diagram.md](../architecture/diagrams/deployment-diagram.md)) — catalogs, not metastores, are what separates dev from staging, since both are non-production; prod gets metastore-level isolation as an additional boundary given its regulated/PII data.
- Data sharing (Delta Sharing) to external consumers (e.g. a regulator, a partner utility) is granted at the `smartmeter_prod.gold` schema level, never at catalog root — least-privilege by construction.
- Tags (e.g. `pii=true`, `retention=7y`) are applied at the schema/table/column level within this structure and drive ABAC policies and column masking (see [security-diagram.md](../architecture/diagrams/security-diagram.md)) — the catalog/schema layout gives tags a predictable place to attach rather than needing per-table ad hoc tagging decisions.
