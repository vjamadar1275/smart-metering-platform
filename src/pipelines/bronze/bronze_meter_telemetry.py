"""Bronze layer: raw, immutable landing of smart meter telemetry from Event Hubs.

Lakeflow Declarative Pipeline (see bundles/bronze_pipeline.yml for deployment,
docs/architecture/ARCHITECTURE.md#2-ingestion--bronze-structured-streaming for
the design, ADR-0009 for why this reads via the Kafka protocol).

Deliberately does no validation, deduplication, or filtering — that is Silver's
job (Phase 4). Every record that reaches Event Hubs lands here, including ones
that fail to parse, so Bronze remains a complete, replayable raw source.
"""

from pathlib import Path

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.avro.functions import from_avro

AVRO_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "avro" / "meter_telemetry.avsc"
AVRO_SCHEMA_JSON = AVRO_SCHEMA_PATH.read_text()

# Populated from the Lakeflow pipeline's `configuration` block (see
# bundles/bronze_pipeline.yml), which is itself populated per-environment
# from src/config/<env>/bronze_pipeline.json — never hardcoded here, per
# CONTRIBUTING.md's "no hardcoded environment values" rule.
_conf = spark.conf
EVENT_HUB_NAMESPACE = _conf.get("smartmeter.event_hub.namespace")
EVENT_HUB_NAME = _conf.get("smartmeter.event_hub.name")
CONSUMER_GROUP = _conf.get("smartmeter.event_hub.consumer_group", "bronze-streaming")
SECRET_SCOPE = _conf.get("smartmeter.secrets.scope")
MAX_OFFSETS_PER_TRIGGER = int(_conf.get("smartmeter.bronze.max_offsets_per_trigger", "2000000"))

_KAFKA_BOOTSTRAP_SERVERS = f"{EVENT_HUB_NAMESPACE}.servicebus.windows.net:9093"


def _kafka_sasl_jaas_config() -> str:
    """Builds the Kafka SASL/PLAIN JAAS config from the Event Hubs connection
    string stored in Key Vault (see terraform/modules/event-hub/main.tf,
    azurerm_key_vault_secret.connection_string). Event Hubs' Kafka endpoint
    authenticates any username with the namespace connection string as the
    password — "$ConnectionString" is Event Hubs' fixed convention, not a
    per-environment secret itself.
    """
    connection_string = dbutils.secrets.get(SECRET_SCOPE, "eventhub-connection-string")
    return (
        "kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required "
        f'username="$ConnectionString" password="{connection_string}";'
    )


@dp.table(
    name="bronze.meter_telemetry",
    comment=(
        "Raw, immutable smart meter telemetry as received from Event Hubs. "
        "Append-only, schema-evolved, exactly-once via Structured Streaming "
        "checkpointing (Lakeflow-managed). See "
        "docs/architecture/ARCHITECTURE.md#2-ingestion--bronze-structured-streaming."
    ),
    table_properties={
        "delta.enableChangeDataFeed": "true",
        "delta.autoOptimize.optimizeWrite": "true",
        "quality": "bronze",
        # New optional fields in schemas/avro/meter_telemetry.avsc (e.g. a
        # future firmware adding a sensor) should land without a manual
        # ALTER TABLE — permissive evolution per ARCHITECTURE.md's Bronze
        # design ("Bronze table uses mergeSchema with a permissive mode").
        "delta.schema.autoMerge.enabled": "true",
    },
    partition_cols=["ingest_date"],
)
def meter_telemetry():
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", _KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", EVENT_HUB_NAME)
        .option("kafka.sasl.mechanism", "PLAIN")
        .option("kafka.security.protocol", "SASL_SSL")
        .option("kafka.sasl.jaas.config", _kafka_sasl_jaas_config())
        .option("kafka.group.id", CONSUMER_GROUP)
        .option("startingOffsets", "earliest")
        # Sized from the capacity plan (docs/architecture/ARCHITECTURE.md#capacity-planning):
        # ~44K events/sec peak at 10M meters; this bounds each micro-batch so
        # backlog catch-up after an outage drains in bounded, predictable steps
        # rather than one unbounded batch.
        .option("maxOffsetsPerTrigger", MAX_OFFSETS_PER_TRIGGER)
        .load()
    )

    parsed = raw.select(
        F.col("key").cast("string").alias("meter_id_partition_key"),
        F.col("value").alias("raw_payload"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("timestamp").alias("kafka_timestamp"),
        # mode="PERMISSIVE": a malformed message yields a null struct rather
        # than failing the stream — raw_payload is retained regardless, so
        # nothing is lost, only left unparsed until Bronze is reprocessed
        # with a fix (see ADR-0009's schema-sync consequence).
        from_avro(F.col("value"), AVRO_SCHEMA_JSON, {"mode": "PERMISSIVE"}).alias("event"),
    )

    return parsed.select(
        F.col("event.meter_id").alias("meter_id"),
        F.col("event.reading_timestamp").alias("reading_timestamp"),
        F.col("event.ingest_timestamp").alias("ingest_timestamp"),
        F.col("event.reading_value").alias("reading_value"),
        F.col("event.unit").alias("unit"),
        F.col("event.flow_rate").alias("flow_rate"),
        F.col("event.battery_pct").alias("battery_pct"),
        F.col("event.signal_quality").alias("signal_quality"),
        F.col("event.dma_id").alias("dma_id"),
        F.col("event.firmware_version").alias("firmware_version"),
        F.col("event.sequence_no").alias("sequence_no"),
        F.col("raw_payload"),
        F.when(F.col("event").isNull(), F.lit("avro_deserialization_failed")).alias("parse_error"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
        F.col("kafka_timestamp"),
        F.coalesce(F.to_date(F.col("event.ingest_timestamp")), F.current_date()).alias(
            "ingest_date"
        ),
        F.current_timestamp().alias("ingested_at"),
    )
