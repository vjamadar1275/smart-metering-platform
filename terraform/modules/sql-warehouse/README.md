# Module: sql-warehouse

Provisions one workload-isolated Serverless SQL Warehouse (`databricks_sql_endpoint`) defined in [ADR-0005](../../../docs/decisions/ADR-0005-sql-warehouse-isolation.md), plus `CAN_USE` grants to the group(s) named in `authorized_group_names`. Called three times from each environment root module — `sqlw-bi`, `sqlw-adhoc`, `sqlw-executive` — with per-warehouse sizing/access.

**Status**: implemented (Phase 6). See `terraform/environments/<env>/main.tf` for the three module calls and their per-environment sizing.

## Sizing per environment

| Warehouse | dev | staging | prod |
|---|---|---|---|
| `sqlw-bi` | 2X-Small, 1-2 clusters | Small, 1-4 clusters | Small, 2-8 clusters |
| `sqlw-adhoc` | 2X-Small, 1-2 clusters | Medium, 1-4 clusters | Medium, 2-6 clusters |
| `sqlw-executive` | 2X-Small, 1 cluster | Small, 1-2 clusters | Small, 2-4 clusters |

Sizing is a starting point, not a final answer — ADR-0005's consequence explicitly calls out that each warehouse should be right-sized once real query patterns are measured (Phase 8 Lakehouse Monitoring / query history).

## Access

`authorized_group_names` expects Entra ID / Databricks account-console group names that already exist (group creation/membership is out of this module's scope) — e.g. `sqlw-executive` is granted to a small named group (`smartmeter-executives`), `sqlw-adhoc` to a broader analyst group (`smartmeter-analysts`), matching ADR-0005's "doubles as a lightweight data-access control layer" consequence.
