"""CLI: generate a synthetic meter population and telemetry readings to local
files, for local Bronze pipeline testing or feeding into the Event Hub
simulator (tools/event_hub_simulator/).

Usage:
    python -m tools.mock_data_generator.cli \\
        --meters 1000 --hours 24 --leak-rate 0.01 \\
        --out-dir ./mock_data
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools.mock_data_generator.generator import (
    generate_meter_master,
    simulate_readings,
    to_epoch_millis,
)


def _meter_to_json(meter) -> dict:
    d = dataclasses.asdict(meter)
    d["install_date"] = meter.install_date.isoformat()
    return d


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meters", type=int, default=1000, help="Number of meters to generate.")
    parser.add_argument("--hours", type=float, default=24, help="Hours of telemetry to simulate.")
    parser.add_argument(
        "--leak-rate",
        type=float,
        default=0.01,
        help="Fraction of meters that develop a simulated leak during the window.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("./mock_data"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    meters = generate_meter_master(args.meters, seed=args.seed)
    rng = random.Random(args.seed)
    leak_meter_ids = frozenset(
        m.meter_id for m in rng.sample(meters, k=max(1, int(len(meters) * args.leak_rate)))
    )

    meter_master_path = args.out_dir / "meter_master.jsonl"
    with meter_master_path.open("w") as f:
        for meter in meters:
            f.write(json.dumps(_meter_to_json(meter)) + "\n")

    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=args.hours)

    readings_path = args.out_dir / "readings.jsonl"
    count = 0
    with readings_path.open("w") as f:
        events = simulate_readings(
            meters, start, end, seed=args.seed, leak_meter_ids=leak_meter_ids
        )
        for event in events:
            event = dict(event)
            event["reading_timestamp"] = to_epoch_millis(event["reading_timestamp"])
            event["ingest_timestamp"] = to_epoch_millis(event["ingest_timestamp"])
            f.write(json.dumps(event) + "\n")
            count += 1

    print(f"Wrote {len(meters)} meters to {meter_master_path}")
    print(f"Wrote {count} readings ({len(leak_meter_ids)} leaking) to {readings_path}")


if __name__ == "__main__":
    main()
