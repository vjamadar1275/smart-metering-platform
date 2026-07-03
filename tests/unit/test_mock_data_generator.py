"""Unit tests for tools/mock_data_generator — pure-Python logic, no Spark/Azure
dependency. Verifies the generator actually produces schema-conformant,
physically-sensible data, since everything downstream (the simulator, local
Bronze testing) trusts this without re-validating it itself.
"""

import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fastavro
import pytest

from tools.mock_data_generator.generator import (
    DMA_IDS,
    MeterState,
    generate_customer_master,
    generate_dma_reference,
    generate_meter_master,
    generate_reading,
    simulate_readings,
    to_epoch_millis,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "avro" / "meter_telemetry.avsc"


@pytest.fixture(scope="module")
def avro_schema():
    return fastavro.parse_schema(json.loads(SCHEMA_PATH.read_text()))


def test_generate_meter_master_produces_unique_ids():
    meters = generate_meter_master(500, seed=1)
    assert len(meters) == 500
    assert len({m.meter_id for m in meters}) == 500


def test_generate_meter_master_is_deterministic_for_a_given_seed():
    a = generate_meter_master(50, seed=7)
    b = generate_meter_master(50, seed=7)
    assert [m.meter_id for m in a] == [m.meter_id for m in b]
    assert [m.dma_id for m in a] == [m.dma_id for m in b]


def test_generated_meters_have_valid_meter_type():
    meters = generate_meter_master(200, seed=2)
    assert {m.meter_type for m in meters} <= {"RESIDENTIAL", "COMMERCIAL", "INDUSTRIAL"}


def test_readings_are_avro_schema_conformant(avro_schema):
    meters = generate_meter_master(20, seed=3)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=6)

    events = list(simulate_readings(meters, start, end, seed=3))
    assert len(events) > 0

    for event in events:
        avro_event = dict(event)
        avro_event["reading_timestamp"] = to_epoch_millis(event["reading_timestamp"])
        avro_event["ingest_timestamp"] = to_epoch_millis(event["ingest_timestamp"])
        buf = io.BytesIO()
        # Raises on any field type/shape mismatch — this is the actual
        # contract check, not just "the dict has the right keys".
        fastavro.schemaless_writer(buf, avro_schema, avro_event)


def test_cumulative_reading_never_decreases():
    meters = generate_meter_master(10, seed=4)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=12)

    last_seen = {}
    for event in simulate_readings(meters, start, end, seed=4, dropout_probability_enabled=False):
        prev = last_seen.get(event["meter_id"], 0.0)
        assert event["reading_value"] >= prev, "cumulative totalizer must never decrease"
        last_seen[event["meter_id"]] = event["reading_value"]


def test_sequence_no_increments_per_meter_without_gaps_when_dropout_disabled():
    meters = generate_meter_master(5, seed=5)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=3)

    counts = {}
    for event in simulate_readings(meters, start, end, seed=5, dropout_probability_enabled=False):
        counts[event["meter_id"]] = counts.get(event["meter_id"], 0) + 1
        assert event["sequence_no"] == counts[event["meter_id"]]


def test_leak_meter_shows_elevated_overnight_flow():
    meter = generate_meter_master(1, seed=6)[0]
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)  # midnight UTC
    end = start + timedelta(hours=6)

    leaking = list(
        simulate_readings([meter], start, end, seed=6, leak_meter_ids=frozenset({meter.meter_id}))
    )
    normal = list(simulate_readings([meter], start, end, seed=6))

    overnight_leak_flow = sum(
        e["flow_rate"] for e in leaking if 2 <= e["reading_timestamp"].hour <= 4
    )
    overnight_normal_flow = sum(
        e["flow_rate"] for e in normal if 2 <= e["reading_timestamp"].hour <= 4
    )

    assert overnight_leak_flow > overnight_normal_flow


def test_dropout_can_skip_an_interval():
    meter = generate_meter_master(1, seed=8)[0]
    state = MeterState(meter=meter)
    import random

    rng = random.Random(0)  # seed chosen so rng.random() < 0.02 fires at least once below
    ts = datetime(2026, 1, 1, tzinfo=UTC)

    results = [
        generate_reading(state, ts + timedelta(minutes=15 * i), rng, inject_dropout=True)
        for i in range(500)
    ]
    assert any(
        r is None for r in results
    ), "expected at least one dropped interval across 500 draws at 2% probability"
    assert any(r is not None for r in results)


def test_generate_customer_master_produces_one_row_per_unique_customer_id():
    meters = generate_meter_master(500, seed=9)
    customers = generate_customer_master(meters, seed=9)
    assert {c.customer_id for c in customers} == {m.customer_id for m in meters}
    assert len(customers) == len({c.customer_id for c in customers})


def test_generate_customer_master_account_type_matches_a_held_meter_type():
    meters = generate_meter_master(200, seed=10)
    customers = generate_customer_master(meters, seed=10)
    meter_types_by_customer = {}
    for m in meters:
        meter_types_by_customer.setdefault(m.customer_id, set()).add(m.meter_type)
    for customer in customers:
        assert customer.account_type in meter_types_by_customer[customer.customer_id]


def test_generate_customer_master_is_deterministic_for_a_given_seed():
    meters = generate_meter_master(100, seed=11)
    a = generate_customer_master(meters, seed=11)
    b = generate_customer_master(meters, seed=11)
    assert [(c.customer_id, c.account_name) for c in a] == [
        (c.customer_id, c.account_name) for c in b
    ]


def test_generate_customer_master_connection_date_not_before_earliest_meter_install():
    meters = generate_meter_master(50, seed=12)
    customers = generate_customer_master(meters, seed=12)
    earliest_install = {}
    for m in meters:
        earliest_install[m.customer_id] = min(
            earliest_install.get(m.customer_id, m.install_date), m.install_date
        )
    for customer in customers:
        assert customer.connection_date >= earliest_install[customer.customer_id]


def test_generate_dma_reference_covers_every_dma_id_exactly_once():
    dmas = generate_dma_reference(seed=13)
    assert [d.dma_id for d in dmas] == DMA_IDS


def test_generate_dma_reference_target_nrw_pct_in_plausible_range():
    dmas = generate_dma_reference(seed=14)
    for dma in dmas:
        assert 0.0 < dma.target_nrw_pct < 100.0
        assert dma.population_served > 0


def test_generate_dma_reference_is_deterministic_for_a_given_seed():
    a = generate_dma_reference(seed=15)
    b = generate_dma_reference(seed=15)
    assert a == b
