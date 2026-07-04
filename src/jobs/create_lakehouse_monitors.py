"""Creates/updates Databricks Lakehouse Monitors on the key Silver/Gold
tables (Phase 8), for the data-quality observability
docs/architecture/diagrams/security-diagram.md's Audit & Compliance layer
and docs/guides/OPERATIONS_GUIDE.md describe.

Monitored tables, all time-series monitors (profiling metrics computed per
time window, so drift/freshness show up as a trend, not just a snapshot):

- silver.meter_readings (timestamp_col=reading_timestamp): the single
  source of truth every Gold table depends on — schema drift or a sudden
  null-rate spike here should be caught before it propagates downstream.
- gold.daily_usage (timestamp_col=reading_date): the base Gold mart most
  other marts roll up from.
- gold.dma_analytics (timestamp_col=reading_date): carries the
  non-revenue-water proxy and night-flow leak indicator (ADR-0011) —
  monitoring this catches e.g. a reference.dim_dma data issue silently
  corrupting the NRW calculation for every DMA at once.

A plain batch Databricks Job task (src/jobs/, not a Lakeflow pipeline —
monitor creation/refresh is inherently a one-off/idempotent setup
operation, not a continuous transformation, same reasoning as
src/jobs/seed_reference_data.py), triggered manually or on a low-frequency
schedule (see bundles/lakehouse_monitoring.yml) since monitored-table
*schemas* change rarely even though the *data* changes continuously —
Lakehouse Monitoring's own refresh schedule (configured per monitor, not
here) is what re-profiles the data itself.

Usage (Databricks Job task):
    python -m src.jobs.create_lakehouse_monitors --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse

MONITORED_TABLES = {
    "silver.meter_readings": "reading_timestamp",
    "gold.daily_usage": "reading_date",
    "gold.dma_analytics": "reading_date",
}


def create_or_update_monitor(workspace_client, table_name: str, timestamp_col: str) -> None:
    """Creates a time-series Lakehouse Monitor on `table_name` if none
    exists yet, else leaves the existing one as-is (monitor *configuration*
    changes — e.g. a new custom metric — are an explicit, reviewed update,
    not something this idempotent setup script silently overwrites).
    """
    from databricks.sdk.service.catalog import MonitorTimeSeries

    try:
        workspace_client.quality_monitors.get(table_name=table_name)
        return  # already exists — leave configuration changes to a deliberate follow-up
    except Exception:
        pass  # not found (or a transient error the create call below will also surface)

    assets_dir_suffix = table_name.replace(".", "_")
    workspace_client.quality_monitors.create(
        table_name=table_name,
        assets_dir=f"/Shared/smart-metering-platform/lakehouse_monitoring/{assets_dir_suffix}",
        output_schema_name=table_name.rsplit(".", 1)[0],
        time_series=MonitorTimeSeries(timestamp_col=timestamp_col, granularities=["1 day"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    args = parser.parse_args()

    from databricks.sdk import WorkspaceClient

    workspace_client = WorkspaceClient()
    for table, timestamp_col in MONITORED_TABLES.items():
        create_or_update_monitor(workspace_client, f"{args.catalog}.{table}", timestamp_col)


if __name__ == "__main__":
    main()
