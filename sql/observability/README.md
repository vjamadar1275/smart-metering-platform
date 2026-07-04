# System-Table-Based Observability

Reference queries over Databricks [system tables](https://docs.databricks.com/en/admin/system-tables/index.html) (`system.billing.*`, `system.query.*`, `system.access.*`) — no ingestion/ETL required, these are Databricks-managed tables already populated from platform activity. Complements [terraform/modules/monitoring](../../terraform/modules/monitoring/) (Azure-side resource logs/metrics) with Databricks-native cost, query-performance, and audit visibility, per [security-diagram.md](../../docs/architecture/diagrams/security-diagram.md)'s Audit & Compliance layer.

| Query | System table | Answers |
|---|---|---|
| [platform_cost_by_sku.sql](platform_cost_by_sku.sql) | `system.billing.usage` | What is this platform's Databricks compute spend by SKU, and how is it trending? |
| [warehouse_query_performance.sql](warehouse_query_performance.sql) | `system.query.history` | Is ADR-0005's workload isolation actually working — do `sqlw-bi`/`sqlw-executive` stay fast regardless of `sqlw-adhoc` load? |
| [audit_log_summary.sql](audit_log_summary.sql) | `system.access.audit` | Who accessed what, and are there anomalous spikes in access to PII-masked/row-filtered objects (`sql/governance/`)? |

These are reference SQL, like [sql/ddl/](../ddl/) — run manually against a live workspace's system catalog (requires `USE CATALOG` on `system`, granted to account admins by default) or wire into a Lakeview dashboard following the same pattern as [sql/dashboards/](../dashboards/). Not mechanically validated against real system-table data in this sandbox (no live Databricks workspace here) — the exact schema of `system.access.audit`'s `request_params` map is documented to vary by `service_name`/`action_name`, so treat `audit_log_summary.sql`'s filter as a starting point to refine once run for real.
