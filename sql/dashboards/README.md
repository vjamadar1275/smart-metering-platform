# Databricks SQL Dashboards (Lakeview)

Three Lakeview dashboards (`.lvdash.json`, Databricks' current native dashboard format), deployed as Databricks Asset Bundle `dashboards` resources — see [bundles/dashboards.yml](../../bundles/dashboards.yml). Each queries Gold tables directly (Phase 5) and routes to the SQL Warehouse matching its consumer per [ADR-0005](../../docs/decisions/ADR-0005-sql-warehouse-isolation.md).

| Dashboard | Audience / warehouse | Built from |
|---|---|---|
| [operational_dashboard.lvdash.json](operational_dashboard.lvdash.json) | Operations team / `sqlw-bi` | `gold.operational_dashboard`, `gold.dma_analytics`, `gold.daily_usage` |
| [executive_dashboard.lvdash.json](executive_dashboard.lvdash.json) | Executives / `sqlw-executive` | `gold.executive_dashboard`, `gold.daily_usage`, `gold.dma_analytics` |
| [consumption_trends.lvdash.json](consumption_trends.lvdash.json) | Analysts / `sqlw-adhoc` | `gold.dma_analytics`, `gold.customer_analytics`, `gold.hourly_consumption` |

## Non-revenue-water caveat

`executive_dashboard.lvdash.json`'s NRW widget and `operational_dashboard.lvdash.json`'s DMA leak table both surface `gold.dma_analytics` columns derived from an **estimated supply proxy**, not real bulk-supply telemetry — see [ADR-0011](../../docs/decisions/ADR-0011-gold-pipeline-split-and-nrw-proxy.md). The widget label says so ("estimate — see ADR-0011") deliberately, so a viewer doesn't mistake it for an audited figure.

## Catalog substitution

Each dataset's SQL query references `${var.catalog_name}` — Databricks Asset Bundles substitute bundle variables inside dashboard JSON at deploy time (same mechanism used for `bundles/*_pipeline.yml`'s `configuration:` blocks), so these files are not meant to be imported standalone; deploy them via `databricks bundle deploy -t <env>` once real Databricks credentials and a deployed Gold layer exist.

## A note on mechanical validation

This repository's sandboxed development environment cannot reach the Databricks CLI download host or a live workspace (see `bundles/README.md` if present, or the Phase 6 commit message), so these `.lvdash.json` files are syntax-validated as JSON but not validated against Databricks' actual Lakeview import schema, which is not fully documented and changes between platform releases. Before relying on them, import each into a real dev workspace (`databricks bundle deploy -t dev` then open the dashboard in the workspace UI) and fix any schema drift the UI surfaces — treat these as a strong starting draft, not a guaranteed-importable artifact.
