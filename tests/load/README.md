# Load Tests

Exercises the Event Hub producer path ([tools/event_hub_simulator/](../../tools/event_hub_simulator/)) at a target sustained throughput against a **real** Event Hub — a genuine load test, not a mock, but skipped (not failed) without live credentials, same pattern as [tests/integration/](../integration/).

| Module | Verifies |
|---|---|
| [test_event_hub_load.py](test_event_hub_load.py) | The simulator sustains at least 80% of a 500 events/sec target for 30 seconds against a real Event Hub. |

## Usage

```bash
export EVENTHUB_CONNECTION_STRING="$(az keyvault secret show \
    --vault-name <dev-key-vault-name> --name evhns-dev-connection-string \
    --query value -o tsv)"
export SMARTMETER_TEST_EVENTHUB_NAME=evh-meter-telemetry
pytest tests/load/test_event_hub_load.py
```

## Scope

This verifies the **producer** side only — that the simulator itself can sustain the target rate. It does not verify Bronze/Silver/Gold keep up with that rate end-to-end; that requires querying pipeline throughput over the same window against a live workspace, which is a manual [Performance Guide](../../docs/guides/PERFORMANCE_GUIDE.md) exercise, not something this test (or CI) can assert on its own without that same live-workspace access [tests/integration/](../integration/) already documents as unavailable in this environment.
