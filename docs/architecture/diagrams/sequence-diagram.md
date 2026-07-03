# Sequence Diagram — End-to-End Meter Reading

Traces a single meter reading from the device to an executive's Power BI dashboard, and separately, the path into an AI-driven leak alert.

```mermaid
sequenceDiagram
    autonumber
    participant Meter as Smart Meter
    participant GW as Field Gateway
    participant EH as Event Hub
    participant Bronze as Bronze Streaming Job
    participant BT as Bronze Delta Table
    participant Silver as Silver Pipeline
    participant ST as Silver Delta Table
    participant Gold as Gold Pipeline
    participant GT as Gold Delta Table
    participant SQLW as SQL Warehouse
    participant PBI as Power BI
    participant AI as Mosaic AI (Anomaly Model)
    participant Ops as Ops Console

    Meter->>GW: Reading (meter_id, ts, value, flow_rate)
    GW->>EH: AMQP publish (Avro, partition key = meter_id)
    EH-->>EH: Durable buffer (Dedicated tier, replicated)

    par Streaming ingestion
        Bronze->>EH: readStream (checkpointed offset)
        EH-->>Bronze: micro-batch of events
        Bronze->>BT: append (exactly-once via checkpoint + Delta ACID)
    and Near-real-time quality signal
        Silver->>BT: readStream (CDF)
        Silver->>Silver: validate / dedupe (MERGE) / enrich
        Silver->>ST: upsert
        Silver->>AI: publish enriched stream (feature pipeline)
        AI->>AI: score anomaly (leak likelihood)
        alt anomaly score > threshold
            AI->>Ops: push alert (webhook / Model Serving inference table)
        end
    end

    Gold->>ST: incremental read (watermark-bounded)
    Gold->>Gold: aggregate (hourly/daily, DMA, customer)
    Gold->>GT: MERGE

    Note over SQLW,PBI: Independent, on-demand — not triggered per-event
    PBI->>SQLW: DAX/SQL query (Direct Lake)
    SQLW->>GT: read (Liquid Clustered, pruned)
    GT-->>SQLW: result set
    SQLW-->>PBI: query result
    PBI-->>PBI: render executive dashboard
```

## Timing Expectations

| Hop | Target latency | Notes |
|---|---|---|
| Meter → Event Hub | Seconds (network-dependent) | Outside platform control |
| Event Hub → Bronze | < 60s | Micro-batch interval |
| Bronze → Silver | < 5 min | Includes validation + dedup MERGE |
| Silver → anomaly alert | < 10 min | Feature computation + model inference |
| Silver → Gold | 15 min – hourly (KPI-dependent) | Hourly KPIs vs. daily KPIs run on different schedules |
| Gold → dashboard | Sub-second | Direct Lake / pre-aggregated Gold |
