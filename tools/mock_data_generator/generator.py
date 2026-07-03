"""Synthetic smart meter master data and 15-minute telemetry readings.

Pure functions with no Spark/Databricks/Azure dependency, so this is testable
in isolation (see tests/unit/test_mock_data_generator.py) and reusable both
by the Event Hub simulator (tools/event_hub_simulator/) and by local
notebook exploration. Output matches schemas/avro/meter_telemetry.avsc.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

DMA_IDS = [f"DMA-{i:03d}" for i in range(1, 21)]
METER_TYPES = ["RESIDENTIAL", "COMMERCIAL", "INDUSTRIAL"]
FIRMWARE_VERSIONS = ["2.4.1", "2.4.2", "2.5.0", "2.5.1"]
READING_INTERVAL_MINUTES = 15

# Baseline hourly consumption weights (residential diurnal curve): low
# overnight, morning peak ~7am, evening peak ~7pm. Index = hour of day.
_DIURNAL_WEIGHTS = [
    0.2,
    0.15,
    0.1,
    0.1,
    0.15,
    0.3,
    0.8,
    1.6,
    1.3,
    0.9,
    0.7,
    0.6,
    0.6,
    0.6,
    0.6,
    0.7,
    0.9,
    1.3,
    1.7,
    1.4,
    1.0,
    0.7,
    0.4,
    0.25,
]


@dataclass(frozen=True)
class Meter:
    meter_id: str
    dma_id: str
    customer_id: str
    meter_type: str
    install_date: date
    latitude: float
    longitude: float
    firmware_version: str
    meter_size_mm: int


@dataclass
class MeterState:
    """Mutable per-meter simulation state: the cumulative totalizer reading
    a real meter never resets, so the generator must track it across calls
    rather than synthesizing each reading independently."""

    meter: Meter
    cumulative_reading: float = 0.0
    sequence_no: int = 0
    battery_pct: int = 100
    leak_active: bool = False


def generate_meter_master(count: int, seed: int = 42) -> list[Meter]:
    """Generates a representative meter population across DMAs and meter types."""
    rng = random.Random(seed)
    meters = []
    for i in range(count):
        meter_type = rng.choices(METER_TYPES, weights=[0.85, 0.12, 0.03])[0]
        install_days_ago = rng.randint(30, 365 * 12)
        meters.append(
            Meter(
                meter_id=f"MTR-{i:08d}",
                dma_id=rng.choice(DMA_IDS),
                customer_id=f"CUST-{rng.randint(1, count):08d}",
                meter_type=meter_type,
                install_date=date.today() - timedelta(days=install_days_ago),
                latitude=round(rng.uniform(29.0, 30.5), 6),
                longitude=round(rng.uniform(-98.5, -97.0), 6),
                firmware_version=rng.choice(FIRMWARE_VERSIONS),
                meter_size_mm=rng.choice([15, 15, 15, 20, 25, 40]),
            )
        )
    return meters


def _base_flow_liters(meter: Meter, ts: datetime, rng: random.Random) -> float:
    """15-minute consumption volume, liters, before anomaly injection."""
    type_multiplier = {"RESIDENTIAL": 1.0, "COMMERCIAL": 4.0, "INDUSTRIAL": 12.0}[meter.meter_type]
    weight = _DIURNAL_WEIGHTS[ts.hour]
    base = 3.0 * type_multiplier * weight
    noise = rng.gauss(1.0, 0.25)
    return max(0.0, base * noise)


def generate_reading(
    state: MeterState,
    reading_timestamp: datetime,
    rng: random.Random,
    inject_leak: bool = False,
    inject_dropout: bool = False,
) -> dict | None:
    """Advances `state` by one 15-minute interval and returns the telemetry
    event dict (matching schemas/avro/meter_telemetry.avsc), or None if this
    interval is dropped (simulating a gateway/connectivity gap for
    late-arrival testing — see ARCHITECTURE.md's Silver watermarking design).
    """
    if inject_dropout and rng.random() < 0.02:
        return None

    volume = _base_flow_liters(state.meter, reading_timestamp, rng)

    state.leak_active = inject_leak and (
        state.leak_active or (2 <= reading_timestamp.hour <= 4 and rng.random() < 0.01)
    )
    if state.leak_active:
        # Classic leak signature: sustained non-zero overnight flow instead
        # of near-zero — the exact DMA night-flow anomaly leak detection
        # (Phase 7 Mosaic AI use case) is meant to catch.
        volume += rng.uniform(8.0, 20.0)

    state.cumulative_reading += volume
    state.sequence_no += 1
    state.battery_pct = max(1, state.battery_pct - rng.choices([0, 1], weights=[0.97, 0.03])[0])

    flow_rate = volume / READING_INTERVAL_MINUTES if volume > 0 else 0.0

    return {
        "meter_id": state.meter.meter_id,
        "reading_timestamp": reading_timestamp,
        "ingest_timestamp": reading_timestamp + timedelta(seconds=rng.randint(1, 45)),
        "reading_value": round(state.cumulative_reading, 3),
        "unit": "LITERS",
        "flow_rate": round(flow_rate, 4),
        "battery_pct": state.battery_pct,
        "signal_quality": rng.randint(40, 100),
        "dma_id": state.meter.dma_id,
        "firmware_version": state.meter.firmware_version,
        "sequence_no": state.sequence_no,
    }


def simulate_readings(
    meters: list[Meter],
    start: datetime,
    end: datetime,
    seed: int = 42,
    leak_meter_ids: frozenset[str] = frozenset(),
    dropout_probability_enabled: bool = True,
) -> Iterator[dict]:
    """Yields telemetry events for every meter at every 15-minute interval in
    [start, end), in timestamp order across the whole population (the order
    an Event Hub simulator would actually publish in), UTC-aware datetimes.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware (UTC)")

    rng = random.Random(seed)
    states = {m.meter_id: MeterState(meter=m) for m in meters}

    interval_count = int((end - start) / timedelta(minutes=READING_INTERVAL_MINUTES))
    for step in range(interval_count):
        ts = start + timedelta(minutes=READING_INTERVAL_MINUTES * step)
        for meter in meters:
            state = states[meter.meter_id]
            event = generate_reading(
                state,
                ts,
                rng,
                inject_leak=meter.meter_id in leak_meter_ids,
                inject_dropout=dropout_probability_enabled,
            )
            if event is not None:
                yield event


def to_epoch_millis(dt: datetime) -> int:
    """Avro `timestamp-millis` logical type is UTC milliseconds since epoch."""
    return math.floor(dt.astimezone(UTC).timestamp() * 1000)
