# Event Hub Simulator

Publishes synthetic meter telemetry to the `meter-telemetry` Event Hub over native AMQP 1.0, standing in for real field gateways during local/dev testing of the Bronze pipeline ([src/pipelines/bronze/bronze_meter_telemetry.py](../../src/pipelines/bronze/bronze_meter_telemetry.py)). See [ADR-0009](../../docs/decisions/ADR-0009-event-hub-connector-protocol.md) for why producers use AMQP while Structured Streaming consumes via Kafka.

## Usage

```bash
pip install -r requirements.txt

export EVENTHUB_CONNECTION_STRING="$(az keyvault secret show \
    --vault-name <dev-key-vault-name> \
    --name evhns-dev-connection-string \
    --query value -o tsv)"

# Mode 1: replay pre-generated readings
python -m tools.mock_data_generator.cli --meters 500 --hours 2 --out-dir ./mock_data
python -m tools.event_hub_simulator.simulator \
    --eventhub-name evh-meter-telemetry \
    --input ./mock_data/readings.jsonl \
    --events-per-second 500

# Mode 2: generate and stream directly, no intermediate file
python -m tools.event_hub_simulator.simulator \
    --eventhub-name evh-meter-telemetry \
    --generate --meters 500 --hours 2 --leak-rate 0.02
```

`--events-per-second` throttles publish rate to simulate realistic ingestion pacing; omit it to publish as fast as the AMQP client allows (useful for backlog/catch-up testing — see [ARCHITECTURE.md's peak-factor discussion](../../docs/architecture/ARCHITECTURE.md#capacity-planning)).

Events are batched per `meter_id` (Event Hubs partition key), preserving per-meter ordering exactly as the architecture assumes.
