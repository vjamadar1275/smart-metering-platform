# Data Flow Diagram

Focuses on data transformations and state, not infrastructure.

```mermaid
flowchart LR
    Meter[Smart Meter Telemetry<br/>Avro events] --> EH[(Event Hub<br/>durable log)]
    EH --> B[(Bronze<br/>raw + parsed columns<br/>partitioned by ingest_date)]

    B -->|CDF read| Val[Validation<br/>range/required-field/referential checks]
    Val -->|pass| Dedup[Deduplication<br/>MERGE on meter_id + reading_ts]
    Val -->|fail| Quar[(Quarantine table<br/>+ reason code)]
    Dedup --> Enrich[Enrichment<br/>+ meter/customer/DMA dimensions<br/>+ unit & timezone normalization]
    Enrich --> S[(Silver<br/>validated single source of truth)]

    S --> AggHour[Hourly aggregation]
    S --> AggDay[Daily aggregation]
    S --> AggDMA[DMA balance calculation<br/>supply vs. metered]
    S --> AggCust[Customer usage trends]

    AggHour --> G1[(gold.hourly_consumption)]
    AggDay --> G2[(gold.daily_usage)]
    AggDMA --> G3[(gold.dma_analytics)]
    AggCust --> G4[(gold.customer_analytics)]

    G1 & G2 --> G5[(gold.operational_dashboard)]
    G3 & G4 --> G6[(gold.executive_dashboard)]

    S --> Feat[Feature engineering<br/>rolling windows, lag features]
    Feat --> FT[(Feature tables)]
    FT --> Fcast[Demand Forecasting Model]
    FT --> Leak[Leak Detection Model]
    FT --> Anom[Anomaly Detection Model]

    G1 & G2 & G3 & G4 --> BI[Power BI semantic models]
    G6 --> RAG[Vector Search Index<br/>KPI summaries + docs]
    RAG --> Agent[NL Analytics Agent]

    Quar -.reviewed by.-> DataSteward[Data Steward<br/>manual/automated remediation]
    DataSteward -.corrected records.-> B
```

## Data Contracts Between Stages

| Boundary | Contract |
|---|---|
| Event Hub → Bronze | Avro schema (Schema Registry-enforced); unknown fields preserved in raw payload column |
| Bronze → Silver | At-least-once from Bronze (dedup happens in Silver); CDF used so Silver only processes changed rows |
| Silver → Gold | Silver is the only table Gold reads business logic from — Gold never reads Bronze directly |
| Silver/Gold → AI | Feature tables are the only sanctioned read path for ML — models never read Bronze/raw directly |
| Gold → BI | Gold tables are pre-joined/pre-aggregated to match each Power BI semantic model 1:1, avoiding BI-side fan-out joins |
