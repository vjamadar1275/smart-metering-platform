"""Gold layer: daily-grain business KPIs, DMA analytics, customer
analytics, and pre-aggregated operational/executive dashboards.

Lakeflow Declarative Pipeline (see bundles/gold_batch_pipeline.yml for
deployment, docs/architecture/ARCHITECTURE.md#4-silver--gold for the
design, ADR-0011 for why this is a triggered/batch pipeline rather than
continuous like gold/gold_hourly_consumption.py, ADR-0004 for the Liquid
Clustering keys).

gold.daily_usage, gold.dma_analytics, and gold.customer_analytics are full
materialized views (recomputed from all of Silver's history on every
triggered run) rather than incrementally-maintained tables: the anomaly/
trend logic in src/libs/common/gold_transforms.py depends on trailing-N-day
window functions, which are simplest and most correct to compute over
complete history each run. At this repository's synthetic dev/staging data
volumes that's cheap; a real fleet-scale deployment would likely need an
incremental/partition-scoped rewrite of these marts — tracked as a Phase 8
performance item in ADR-0011, not solved here.

gold.operational_dashboard and gold.executive_dashboard are small,
single/few-row snapshot marts built from the tables above, tuned for
specific Power BI reports (Phase 6).
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from src.libs.common.gold_transforms import (
    compute_customer_analytics,
    compute_daily_usage,
    compute_dma_analytics,
    compute_dma_night_flow,
    compute_executive_dashboard,
    compute_operational_dashboard,
)

_conf = spark.conf
CATALOG = _conf.get("smartmeter.catalog_name")

SILVER_TABLE = f"{CATALOG}.silver.meter_readings"
QUARANTINE_TABLE = f"{CATALOG}.quarantine.silver_meter_readings"
DIM_DMA_TABLE = f"{CATALOG}.reference.dim_dma"


def _latest_available_date(df, date_col: str):
    """Scalar max(date_col) — used to scope the snapshot marts
    (operational/executive dashboards) to the most recently *complete*
    day available, rather than assuming this pipeline always runs at a
    fixed time relative to midnight (robust to a late/early/skipped run).
    """
    return df.agg(F.max(date_col).alias("d")).first()["d"]


@dp.table(
    name="gold.daily_usage",
    comment=(
        "Per-meter, per-day usage with a trailing-7-day baseline and "
        "usage-anomaly flag. See docs/architecture/ARCHITECTURE.md#4-silver--gold."
    ),
    table_properties={"quality": "gold"},
    cluster_by=["meter_id", "reading_date"],
)
def daily_usage():
    readings = spark.read.table(SILVER_TABLE)
    return compute_daily_usage(readings)


@dp.table(
    name="gold.dma_analytics",
    comment=(
        "District Meter Area balance and leak indicators — non-revenue-water "
        "estimate and night-flow anomaly flag per DMA per day. "
        "estimated_supply_liters is a documented proxy (see "
        "src/libs/common/gold_transforms.py:compute_dma_analytics and "
        "ADR-0011) pending a real bulk-supply meter integration."
    ),
    table_properties={"quality": "gold"},
    cluster_by=["dma_id", "reading_date"],
)
def dma_analytics():
    daily_usage_df = dp.read("daily_usage")
    night_flow = compute_dma_night_flow(spark.read.table(SILVER_TABLE))
    dim_dma = spark.read.table(DIM_DMA_TABLE)
    return compute_dma_analytics(daily_usage_df, night_flow, dim_dma)


@dp.table(
    name="gold.customer_analytics",
    comment=(
        "Customer-level usage trends and billing-relevant aggregates, "
        "rolled up from gold.daily_usage. See "
        "docs/architecture/ARCHITECTURE.md#4-silver--gold."
    ),
    table_properties={"quality": "gold"},
    cluster_by=["customer_id", "reading_date"],
)
def customer_analytics():
    daily_usage_df = dp.read("daily_usage")
    return compute_customer_analytics(daily_usage_df)


@dp.table(
    name="gold.operational_dashboard",
    comment=(
        "Fleet-health snapshot for the operations team: today's ingestion "
        "volume, low-battery meters, quarantine rate, and DMA leak-flag "
        "count. One row per pipeline run — tuned for a Phase 6 Power BI "
        "operational report, not for historical trend queries (see "
        "gold.daily_usage/gold.dma_analytics for those)."
    ),
    table_properties={"quality": "gold"},
)
def operational_dashboard():
    readings_today = spark.read.table(SILVER_TABLE).where("reading_date = current_date()")
    quarantine_today = spark.read.table(QUARANTINE_TABLE).where(
        "date(quarantined_at) = current_date()"
    )
    dma_analytics_latest = dp.read("dma_analytics")
    latest_date = _latest_available_date(dma_analytics_latest, "reading_date")
    dma_analytics_today = dma_analytics_latest.where(F.col("reading_date") == latest_date)
    return compute_operational_dashboard(readings_today, quarantine_today, dma_analytics_today)


@dp.table(
    name="gold.executive_dashboard",
    comment=(
        "Top-line KPI mart for executive reporting: total volume, "
        "systemwide non-revenue-water rate, volume by customer segment, "
        "and high-usage customer count, for the most recently complete "
        "day. Tuned for a Phase 6 Power BI executive report."
    ),
    table_properties={"quality": "gold"},
)
def executive_dashboard():
    daily_usage_df = dp.read("daily_usage")
    dma_analytics_df = dp.read("dma_analytics")
    customer_analytics_df = dp.read("customer_analytics")

    latest_date = _latest_available_date(daily_usage_df, "reading_date")
    return compute_executive_dashboard(
        daily_usage_df.where(F.col("reading_date") == latest_date),
        dma_analytics_df.where(F.col("reading_date") == latest_date),
        customer_analytics_df.where(F.col("reading_date") == latest_date),
    )
