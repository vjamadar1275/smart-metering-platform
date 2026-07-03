"""Gold layer: per-meter, per-hour volumetric usage.

Lakeflow Declarative Pipeline (see bundles/gold_streaming_pipeline.yml for
deployment, docs/architecture/ARCHITECTURE.md#4-silver--gold for the
design, ADR-0011 for why this KPI is streaming while the rest of Gold is a
triggered batch pipeline, ADR-0004 for the Liquid Clustering key).

The only Gold table with a Silver latency-comparable SLA: hourly rollups
are useful to operations well before a full day closes, unlike
gold.daily_usage and the marts built on it (gold/gold_daily_marts.py),
which need a day's worth of Silver data to mean anything and tolerate a
batch/triggered cadence instead.
"""

from pyspark import pipelines as dp

from src.libs.common.gold_transforms import compute_hourly_consumption

_conf = spark.conf
CATALOG = _conf.get("smartmeter.catalog_name")
# Wider than Silver's own 24h watermark (ADR-0010): a reading can land in
# Silver up to ~24h late via the nightly reconciliation job, so this
# window must stay open long enough to still catch it in the hour it
# actually belongs to, not just readings that were on time into Silver.
WATERMARK_DURATION = _conf.get("smartmeter.gold.hourly_watermark_duration", "26 hours")

SILVER_TABLE = f"{CATALOG}.silver.meter_readings"


@dp.table(
    name="gold.hourly_consumption",
    comment=(
        "Per-meter, per-hour volumetric usage — the finest-grain Gold KPI, "
        "streamed continuously from silver.meter_readings. See "
        "docs/architecture/ARCHITECTURE.md#4-silver--gold."
    ),
    table_properties={
        "quality": "gold",
    },
    # Liquid Clustering — ADR-0004. meter_id supports "usage history for
    # meter X"; hour_start supports time-range dashboard queries.
    cluster_by=["meter_id", "hour_start"],
)
def hourly_consumption():
    readings = spark.readStream.table(SILVER_TABLE).withWatermark(
        "reading_timestamp", WATERMARK_DURATION
    )
    return compute_hourly_consumption(readings)
