"""Publishes synthetic meter telemetry to Azure Event Hubs over native AMQP
1.0 (azure-eventhub SDK), matching the protocol choice in ADR-0009 for
producers (Structured Streaming, the consumer, instead reads via Kafka —
see src/pipelines/bronze/bronze_meter_telemetry.py).

Two modes:
  --input readings.jsonl   Replay pre-generated readings (tools/mock_data_generator/cli.py)
  --generate               Generate and stream directly, without touching disk

Authentication: connection string only, sourced from the
EVENTHUB_CONNECTION_STRING environment variable or --connection-string —
never hardcoded, matching CONTRIBUTING.md's secrets convention. In a real
deployment this is the same secret Terraform writes to Key Vault
(terraform/modules/event-hub/main.tf's azurerm_key_vault_secret.connection_string).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fastavro
from azure.eventhub import EventData, EventHubProducerClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "avro" / "meter_telemetry.avsc"


def _load_schema(schema_path: Path) -> dict:
    return fastavro.parse_schema(json.loads(schema_path.read_text()))


def _serialize(schema: dict, event: dict) -> bytes:
    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, schema, event)
    return buf.getvalue()


def _events_from_file(path: Path) -> Iterator[dict]:
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _events_from_generator(
    meters: int, hours: float, leak_rate: float, seed: int
) -> Iterator[dict]:
    # Imported lazily so `--input` mode has no dependency on the generator module.
    from tools.mock_data_generator.generator import (
        generate_meter_master,
        simulate_readings,
        to_epoch_millis,
    )

    meter_list = generate_meter_master(meters, seed=seed)
    rng = random.Random(seed)
    leak_meter_ids = frozenset(
        m.meter_id for m in rng.sample(meter_list, k=max(1, int(len(meter_list) * leak_rate)))
    )
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    for event in simulate_readings(
        meter_list, start, end, seed=seed, leak_meter_ids=leak_meter_ids
    ):
        event = dict(event)
        event["reading_timestamp"] = to_epoch_millis(event["reading_timestamp"])
        event["ingest_timestamp"] = to_epoch_millis(event["ingest_timestamp"])
        yield event


def publish(
    producer: EventHubProducerClient,
    schema: dict,
    events: Iterable[dict],
    events_per_second: float | None,
) -> int:
    """Batches events by partition key (meter_id) — Event Hubs guarantees a
    given partition key always maps to the same partition, so this preserves
    per-meter ordering exactly as ARCHITECTURE.md's ingestion design assumes.
    """
    sent = 0
    batch: EventHubProducerClient | None = None
    current_key = None
    interval = (1.0 / events_per_second) if events_per_second else 0.0

    for event in events:
        key = event["meter_id"]
        payload = _serialize(schema, event)

        if batch is None or key != current_key:
            if batch is not None:
                producer.send_batch(batch)
                sent += len(batch)
            batch = producer.create_batch(partition_key=key)
            current_key = key

        try:
            batch.add(EventData(payload))
        except ValueError:
            # Batch is full for this partition key — flush and start a new one.
            producer.send_batch(batch)
            sent += len(batch)
            batch = producer.create_batch(partition_key=key)
            batch.add(EventData(payload))

        if interval:
            time.sleep(interval)

    if batch is not None and len(batch) > 0:
        producer.send_batch(batch)
        sent += len(batch)

    return sent


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("EVENTHUB_CONNECTION_STRING"),
        help="Event Hubs namespace connection string. Defaults to $EVENTHUB_CONNECTION_STRING.",
    )
    parser.add_argument("--eventhub-name", required=True, help="e.g. evh-meter-telemetry")
    parser.add_argument("--schema-path", type=Path, default=DEFAULT_SCHEMA_PATH)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--input", type=Path, help="Path to a readings.jsonl produced by the mock data generator."
    )
    mode.add_argument(
        "--generate", action="store_true", help="Generate and stream readings directly."
    )

    parser.add_argument("--meters", type=int, default=1000, help="(--generate only)")
    parser.add_argument("--hours", type=float, default=1, help="(--generate only)")
    parser.add_argument("--leak-rate", type=float, default=0.01, help="(--generate only)")
    parser.add_argument("--seed", type=int, default=42, help="(--generate only)")
    parser.add_argument(
        "--events-per-second",
        type=float,
        default=None,
        help="Throttle publish rate. Omit for best-effort (fastest possible).",
    )
    args = parser.parse_args()

    if not args.connection_string:
        parser.error(
            "No connection string: pass --connection-string or set EVENTHUB_CONNECTION_STRING."
        )

    schema = _load_schema(args.schema_path)
    events = (
        _events_from_file(args.input)
        if args.input
        else _events_from_generator(args.meters, args.hours, args.leak_rate, args.seed)
    )

    producer = EventHubProducerClient.from_connection_string(
        conn_str=args.connection_string, eventhub_name=args.eventhub_name
    )
    with producer:
        sent = publish(producer, schema, events, args.events_per_second)

    print(f"Published {sent} events to {args.eventhub_name}.")


if __name__ == "__main__":
    main()
