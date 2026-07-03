# Component Diagram

Shows the logical software components and their direct dependencies, independent of physical deployment (see [Deployment Diagram](deployment-diagram.md) for that view).

```mermaid
flowchart TB
    subgraph FieldGW["Field Gateway (out of scope — 3rd party)"]
        GW[Cellular/LPWAN Gateway]
    end

    subgraph EventHub["Azure Event Hubs Namespace"]
        EHNS[Event Hub: meter-telemetry<br/>200+ partitions]
        SR[Schema Registry<br/>Avro schemas]
    end

    subgraph Databricks["Azure Databricks Workspace"]
        subgraph Ingestion["Ingestion Components"]
            BronzeStream[Bronze Streaming Job<br/>Lakeflow Pipeline]
        end

        subgraph Transform["Transform Components"]
            SilverPipe[Silver Pipeline<br/>validate / dedupe / enrich]
            GoldPipe[Gold Pipeline<br/>KPI aggregation]
            DQ[Data Quality Engine<br/>Lakeflow Expectations]
        end

        subgraph Serving["Serving Components"]
            SQLW_BI[SQL Warehouse: BI]
            SQLW_AH[SQL Warehouse: Ad Hoc]
            SQLW_EXEC[SQL Warehouse: Executive]
        end

        subgraph AIComponents["AI Components"]
            FeatureStore[Feature Tables<br/>Unity Catalog]
            MLflowReg[MLflow Model Registry]
            ModelServe[Model Serving Endpoints]
            VecSearch[Mosaic AI Vector Search Index]
            Agent[Agentic AI / NL Analytics Assistant]
        end

        subgraph GovComponents["Governance Components"]
            UC[Unity Catalog<br/>metastore, ACLs, lineage]
            LHMon[Lakehouse Monitoring]
            SysTables[System Tables<br/>audit, billing, lineage]
        end
    end

    subgraph Consumers["Consumers"]
        PBI[Power BI]
        OpsConsole[Operations Console]
        CustomerPortal[Customer Portal]
        Analysts[Data Analysts]
        Execs[Executives]
    end

    GW -->|AMQP 1.0, Avro| EHNS
    EHNS <-.validates against.-> SR
    EHNS --> BronzeStream
    BronzeStream --> SilverPipe
    SilverPipe --> DQ
    DQ --> GoldPipe
    GoldPipe --> SQLW_BI & SQLW_AH & SQLW_EXEC
    GoldPipe --> FeatureStore
    SilverPipe --> FeatureStore
    FeatureStore --> MLflowReg --> ModelServe
    FeatureStore --> VecSearch --> Agent
    ModelServe --> OpsConsole
    Agent --> OpsConsole
    Agent --> CustomerPortal
    SQLW_BI --> PBI --> Execs
    SQLW_AH --> Analysts
    SQLW_EXEC --> PBI

    UC -.governs.-> BronzeStream
    UC -.governs.-> SilverPipe
    UC -.governs.-> GoldPipe
    UC -.governs.-> FeatureStore
    UC -.governs.-> VecSearch
    LHMon -.monitors.-> SilverPipe
    LHMon -.monitors.-> GoldPipe
    SysTables -.audits.-> UC
```

## Component Responsibilities

| Component | Responsibility | Owning phase |
|---|---|---|
| Event Hub namespace + Schema Registry | Durable, ordered, schema-validated ingestion buffer | Phase 3 |
| Bronze Streaming Job | Exactly-once landing of raw telemetry into Delta | Phase 3 |
| Silver Pipeline + Data Quality Engine | Cleansing, dedup, enrichment, quarantine of bad records | Phase 4 |
| Gold Pipeline | Business KPI and mart computation | Phase 5 |
| SQL Warehouses (BI/Ad Hoc/Executive) | Isolated, right-sized query compute per consumer class | Phase 6 |
| Feature Tables, MLflow Registry, Model Serving, Vector Search, Agent | ML/AI use cases (leak detection, forecasting, RAG, NL assistant) | Phase 7 |
| Unity Catalog, Lakehouse Monitoring, System Tables | Cross-cutting governance, quality monitoring, audit | Phases 2 & 8 |
