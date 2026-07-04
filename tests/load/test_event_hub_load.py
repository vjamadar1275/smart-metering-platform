"""Load test: publishes synthetic telemetry to a real Event Hub via
tools/event_hub_simulator and verifies sustained throughput meets a target
rate — a real load test, not a mock, but skipped without live Event Hub
credentials (same pattern as tests/integration/, see that directory's
README for why).

This does NOT verify Bronze/Silver/Gold actually process the load
correctly at this rate end-to-end — that would additionally require
querying Bronze's ingestion rate over the same window, which needs the
same live-workspace access tests/integration/test_silver_pipeline_integration.py
already documents as unavailable here. This test verifies the *producer*
side only: can the simulator sustain the target publish rate against a
real Event Hub. Confirming the *consumer* side keeps up is a Phase 8
Performance Guide exercise run manually against a real dev environment,
not something CI can assert on its own.

Usage:
    export EVENTHUB_CONNECTION_STRING="$(az keyvault secret show ...)"
    export SMARTMETER_TEST_EVENTHUB_NAME=evh-meter-telemetry
    pytest tests/load/test_event_hub_load.py
"""

from __future__ import annotations

import itertools
import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("EVENTHUB_CONNECTION_STRING"),
    reason=(
        "Requires a live Event Hub (EVENTHUB_CONNECTION_STRING) — not available in this "
        "sandbox/CI run. See tools/event_hub_simulator/README.md for how to provision one."
    ),
)

EVENTHUB_NAME = os.environ.get("SMARTMETER_TEST_EVENTHUB_NAME", "evh-meter-telemetry")
TARGET_EVENTS_PER_SECOND = 500
TEST_DURATION_SECONDS = 30
TOTAL_EVENTS = TARGET_EVENTS_PER_SECOND * TEST_DURATION_SECONDS
# A real load run should sustain close to the target rate; this test
# treats "close" as 80% — network/broker variance means demanding exactly
# 100% would make the test flaky for reasons that aren't actual
# regressions.
MIN_ACCEPTABLE_THROUGHPUT_RATIO = 0.8


def test_simulator_sustains_target_publish_rate():
    from datetime import UTC, datetime, timedelta

    from azure.eventhub import EventHubProducerClient

    from tools.event_hub_simulator.simulator import DEFAULT_SCHEMA_PATH, _load_schema, publish
    from tools.mock_data_generator.generator import generate_meter_master, simulate_readings

    # Enough meters/hours that at least TOTAL_EVENTS events exist before
    # truncating with islice — simulate_readings yields one event per
    # meter per 15-minute interval, in timestamp order across the fleet.
    meters = generate_meter_master(count=2000, seed=1)
    start_ts = datetime.now(UTC)
    end_ts = start_ts + timedelta(hours=6)
    events = itertools.islice(simulate_readings(meters, start_ts, end_ts, seed=1), TOTAL_EVENTS)

    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    producer = EventHubProducerClient.from_connection_string(
        conn_str=os.environ["EVENTHUB_CONNECTION_STRING"], eventhub_name=EVENTHUB_NAME
    )

    start = time.perf_counter()
    with producer:
        published_count = publish(producer, schema, events, TARGET_EVENTS_PER_SECOND)
    elapsed = time.perf_counter() - start

    actual_rate = published_count / elapsed
    min_acceptable_rate = TARGET_EVENTS_PER_SECOND * MIN_ACCEPTABLE_THROUGHPUT_RATIO
    assert published_count == TOTAL_EVENTS
    assert actual_rate >= min_acceptable_rate, (
        f"Sustained {actual_rate:.0f} events/sec, below the {min_acceptable_rate:.0f}/sec "
        f"floor ({MIN_ACCEPTABLE_THROUGHPUT_RATIO * 100:.0f}% of the "
        f"{TARGET_EVENTS_PER_SECOND}/sec target)"
    )
