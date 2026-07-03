# Power BI Semantic Model

A source-controlled Power BI semantic model (TMDL format) mapping 1:1 to the six Gold tables (Phase 5), per [ARCHITECTURE.md § Serving](../docs/architecture/ARCHITECTURE.md#5-serving) and [ADR-0005](../docs/decisions/ADR-0005-sql-warehouse-isolation.md).

```
power_bi/
└── SmartMeteringSemanticModel.SemanticModel/
    ├── definition.pbism
    └── definition/
        ├── database.tmdl
        ├── model.tmdl              Model-level settings + table/relationship/expression refs
        ├── expressions.tmdl        Shared data source (parameterized Databricks connection)
        ├── relationships.tmdl      DateDimension -> each fact table's date column
        └── tables/
            ├── DailyUsage.tmdl              <- gold.daily_usage
            ├── HourlyConsumption.tmdl       <- gold.hourly_consumption
            ├── DmaAnalytics.tmdl            <- gold.dma_analytics
            ├── CustomerAnalytics.tmdl       <- gold.customer_analytics
            ├── OperationalDashboard.tmdl    <- gold.operational_dashboard
            ├── ExecutiveDashboard.tmdl      <- gold.executive_dashboard
            └── DateDimension.tmdl           calculated (DAX CALENDAR), Import mode
```

## Why no `.pbip` / `.Report` folder

This ships the **semantic model only**, not a pre-built report with visual pages — Databricks SQL dashboards (Lakeview, [sql/dashboards/](../sql/dashboards/)) already cover the equivalent visualizations for this phase, and a full Power BI report's page-layout JSON is large, mostly-visual, and not something reviewable as plain-text source in the way a semantic model's tables/measures/relationships are. A `.pbip` pointer file conventionally references a paired `.Report` folder; shipping one without a matching report would fail to open in Power BI Desktop, so it's omitted rather than faked.

To use this model:
- **Fabric workspace Git integration**: connect a Fabric workspace to this repo/path and sync `SmartMeteringSemanticModel.SemanticModel/` directly — Fabric supports semantic-model-only Git items, no paired report required.
- **Tabular Editor 2/3**: "File → Open → Folder" against `SmartMeteringSemanticModel.SemanticModel/definition/` opens the TMDL project directly for editing/validation.
- **Power BI Desktop**: create a new report and connect it to this semantic model as a Power BI dataset (Live Connect) once the model is deployed/published, or pair it with a new `.Report` folder locally.

## Data source parameters

Three text parameters (`expressions.tmdl`) — set these to real values before the model can connect to anything:

| Parameter | Value source |
|---|---|
| `Databricks Host` | `terraform output -raw databricks_workspace_url` (`terraform/environments/<env>`) |
| `Databricks HTTP Path` | Derived from `terraform output sql_warehouse_ids` — the `bi` warehouse's HTTP path (`/sql/1.0/warehouses/<id>`) |
| `Catalog Name` | `smartmeter_dev` / `smartmeter_staging` / `smartmeter_prod` |

## DirectQuery now, Direct Lake as the target — an open item

Every table's partition in this model is `mode: directQuery` against `sqlw-bi`. [ARCHITECTURE.md](../docs/architecture/ARCHITECTURE.md#5-serving) names **Direct Lake** (Power BI/Fabric reading Delta Parquet files directly, no SQL Warehouse round-trip) as the intended mode for tables that map 1:1 to Gold — this model doesn't implement that yet. Direct Lake's exact TMDL/M wiring against a **Databricks Unity Catalog** source (as opposed to a native Microsoft Fabric Lakehouse, which is what most published Direct Lake documentation/examples target) has enough version-to-version variance that committing an unverified guess as `mode: directLake` risked being actively misleading rather than merely incomplete. DirectQuery via `sqlw-bi` is correct, well-documented, and gets Phase 6 to a working state; switching specific tables to Direct Lake once validated against a real Fabric/Power BI workspace connected to this platform's Unity Catalog is a tracked follow-up, not a silent gap — same spirit as [ADR-0011](../docs/decisions/ADR-0011-gold-pipeline-split-and-nrw-proxy.md)'s non-revenue-water proxy caveat.

## Relationships

A star-ish shape, deliberately **not** a full snowflake: `DailyUsage`, `DmaAnalytics`, `CustomerAnalytics`, and `HourlyConsumption` each relate to a calculated `DateDimension` table (single-column, on date) for time-intelligence measures (e.g. `TOTALYTD`). `DmaAnalytics` and `CustomerAnalytics` are **not** related to `DailyUsage` directly — both are already pre-aggregated at their own grain (per-DMA-per-day, per-customer-per-day), and relating them to `DailyUsage`'s finer per-meter-per-day grain by `dma_id`/`customer_id` alone (without also constraining by date) would fan out incorrectly across every date in scope. `OperationalDashboard` and `ExecutiveDashboard` are unrelated snapshot tables (one row per pipeline run) — they're meant to be read as-is via their measures, not filtered by report-level slicers.

## Mechanical validation

Not opened in a real Power BI Desktop/Fabric workspace from this sandboxed environment — no Power BI tooling is available here, and (as with `sql/dashboards/`) this repository currently has no live Databricks workspace to connect to. TMDL syntax was hand-verified against the documented format; validate by opening in Tabular Editor or Power BI Desktop before treating this as deployment-ready, and expect to fix any drift the tooling surfaces.
