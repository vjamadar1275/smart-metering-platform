# ADR-0005: Workload-Isolated SQL Warehouses

## Status
Accepted

## Context
Gold and Silver tables are queried by several distinct consumer classes with very different characteristics: scheduled BI dashboard refreshes (predictable, frequent, small queries), ad hoc analyst exploration (unpredictable, occasionally large/expensive), and executive dashboards (business-critical, low tolerance for latency or being queued behind another workload). Running all of this on one shared SQL Warehouse risks one workload class degrading another's SLA and makes cost attribution by consumer impossible.

Options considered:

1. **One shared SQL Warehouse** for all SQL consumption
2. **Workload-isolated SQL Warehouses**: separate warehouses for BI, ad hoc/analyst, and executive reporting
3. **Per-team SQL Warehouses** (isolation by org unit rather than by workload shape)

## Decision
Provision **three purpose-specific Serverless SQL Warehouses**: `sqlw-bi` (scheduled Power BI refreshes against Gold), `sqlw-adhoc` (analyst exploration against Silver/Gold, larger and less auto-stop-aggressive), and `sqlw-executive` (executive dashboards, smallest but highest priority / fastest autoscale, isolated so it's never queued behind an analyst's runaway query).

## Rationale

- **vs. one shared warehouse**: a single warehouse means an analyst's exploratory `SELECT *` with an accidental cross join can exhaust concurrency slots and queue an executive's dashboard load — an availability incident caused by resource contention rather than a real platform failure. This is the single most common cause of "the dashboard is slow" complaints in shared-warehouse Databricks SQL deployments, and it's avoidable structurally rather than through query governance alone.
- **vs. per-team isolation**: isolating by *workload shape* (predictable-small vs. unpredictable-variable vs. business-critical-small) produces better right-sizing than isolating by *org unit*, because two different teams both running predictable small BI queries have the same warehouse-sizing needs — splitting them by team would just duplicate the same warehouse configuration under different names without a corresponding operational benefit. Workload-shape isolation is also what maps cleanly to cost attribution: cost per workload class, not per team, is what the finance/cost-optimization conversation (see [Cost Model Summary](../architecture/ARCHITECTURE.md#cost-model-summary)) actually needs.
- **Serverless for all three**: Serverless SQL Warehouses autoscale in seconds and auto-stop when idle, which matters differently per warehouse — `sqlw-bi` benefits from fast cold-start for scheduled refreshes that shouldn't wait on cluster provisioning; `sqlw-executive` benefits from guaranteed fast response without pre-warming a classic warehouse 24/7; `sqlw-adhoc` benefits from being able to scale up during business hours and fully stop overnight.

## Consequences

- Three warehouses to size, monitor, and cost-attribute instead of one — accepted as the cost of avoiding cross-workload contention; each is independently right-sized (see Phase 6 for concrete SKU/cluster-count sizing once real query patterns are measured).
- Access to each warehouse is itself a Unity Catalog / workspace permission boundary — `sqlw-adhoc` access is broader (all analysts) than `sqlw-executive` (a small named group), which doubles as a lightweight data-access control layer on top of table-level grants.
- Requires query routing discipline: Power BI semantic models must be configured to point at `sqlw-bi` (or `sqlw-executive` for the executive report specifically), not whichever warehouse happens to be running — enforced via Power BI gateway/dataset configuration in Phase 6.
