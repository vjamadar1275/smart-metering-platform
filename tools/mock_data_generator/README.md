# Mock Data Generator

Synthetic smart meter master data and 15-minute telemetry readings, matching [schemas/avro/meter_telemetry.avsc](../../schemas/avro/meter_telemetry.avsc). Pure Python, no Spark/Azure dependency — usable standalone or as input to the [Event Hub simulator](../event_hub_simulator/).

Simulates a residential/commercial/industrial diurnal consumption curve (morning + evening peaks, low overnight), per-meter monotonically increasing cumulative readings, occasional connectivity dropouts (for Silver's late-arrival/watermarking testing), and injected leaks (sustained non-zero overnight flow — the night-flow signature Phase 7's leak-detection model targets).

## Usage

```bash
pip install -r requirements.txt   # only needed for the schema-conformance test

python -m tools.mock_data_generator.cli \
    --meters 1000 \
    --hours 24 \
    --leak-rate 0.01 \
    --out-dir ./mock_data

# -> ./mock_data/meter_master.jsonl
# -> ./mock_data/readings.jsonl
```

## As a library

```python
from tools.mock_data_generator.generator import generate_meter_master, simulate_readings
from datetime import datetime, timezone, timedelta

meters = generate_meter_master(count=100)
start = datetime.now(timezone.utc)
for event in simulate_readings(meters, start, start + timedelta(hours=1)):
    ...  # dict matching schemas/avro/meter_telemetry.avsc
```

### Reference/dimension data (Silver, Phase 4)

`generate_customer_master(meters)` and `generate_dma_reference()` generate the
customer and District Meter Area populations that back
`reference.dim_customer`/`reference.dim_dma` — see
[src/jobs/seed_reference_data.py](../../src/jobs/seed_reference_data.py),
which uses this module (plus `generate_meter_master`) to seed
`reference.dim_meter`/`dim_customer`/`dim_dma` for dev/staging. `Customer`
and `Dma` are the corresponding dataclasses, matching `Meter`'s shape.
