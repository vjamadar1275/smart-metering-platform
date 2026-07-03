# Disaster Recovery Architecture

Strategy: **warm standby** in a paired Azure region. Not active-active (cost of running duplicate streaming compute continuously is not justified against the RTO target), not cold/backup-restore-only (RTO would exceed the < 1 hour streaming-path target).

```mermaid
flowchart TB
    subgraph Normal["Normal Operations — East US 2 (Primary)"]
        EH1[Event Hubs<br/>Dedicated, Geo-DR primary]
        ADLS1[ADLS Gen2<br/>GZRS]
        DBX1[Databricks Workspace<br/>active streaming + batch jobs]
        UC1[Unity Catalog Metastore]
    end

    subgraph Standby["Warm Standby — Central US (Secondary)"]
        EH2[Event Hubs<br/>Geo-DR secondary alias]
        ADLS2[ADLS Gen2<br/>GZRS geo-replica]
        DBX2[Databricks Workspace<br/>provisioned, jobs deployed but stopped]
    end

    EH1 -.async metadata replication.-> EH2
    ADLS1 -.async GZRS replication<br/>RPO ~ minutes.-> ADLS2
    DBX1 -.Terraform + Asset Bundle<br/>config parity.-> DBX2

    subgraph Failover["Failover Sequence (triggered on regional outage)"]
        F1[1: Detect regional outage<br/>Azure Monitor + manual confirmation]
        F2[2: Initiate Event Hub Geo-DR failover<br/>alias repoints to secondary namespace]
        F3[3: Field gateways reconnect<br/>using same alias FQDN — no config change]
        F4[4: Start standby Structured Streaming jobs<br/>resume from last Delta checkpoint in ADLS2]
        F5[5: Validate Unity Catalog metastore<br/>attach / re-attach to secondary workspace]
        F6[6: Re-point SQL Warehouses + Power BI<br/>gateway connections to secondary workspace]
        F7[7: Resume Gold pipelines + AI serving]
    end

    F1 --> F2 --> F3 --> F4 --> F5 --> F6 --> F7
```

## Recovery Objectives

| Component | RPO | RTO | Mechanism |
|---|---|---|---|
| Event Hub (in-flight events) | Seconds (Geo-DR replication lag) | < 15 min | Geo-Disaster Recovery alias failover (metadata + config, not data — Dedicated tier retains enough buffer that a fast failover avoids data loss for events not yet consumed) |
| ADLS Gen2 (Bronze/Silver/Gold + checkpoints) | Near-zero (GZRS is zone-redundant sync in-region; cross-region async, minutes) | < 30 min to confirm replica consistency | GZRS geo-replication; Delta's transaction log ensures the replica is always at a consistent commit boundary, never mid-write |
| Streaming pipelines | Zero (resumes from last committed checkpoint) | < 1 hour | Checkpoints stored in replicated ADLS; standby jobs pre-deployed via Asset Bundles, started on failover |
| Unity Catalog metadata | Near-zero | < 30 min | Metastore is regional; DR runbook re-attaches secondary workspace to a metastore replica / re-registers catalogs (see [runbooks/dr-failover.md](../runbooks/dr-failover.md) — added in Phase 8) |
| BI / AI serving | N/A | < 4 hours | Full restoration is lowest priority — dependent on pipelines being healthy first |

## Backup Strategy (independent of regional DR)

- **Delta Time Travel** (default 30-day log retention, extended to 90 days for Gold via table property) covers accidental-write/logic-bug recovery without invoking full DR.
- **Deep clones** of Gold tables taken weekly to a separate, access-restricted schema — protects against a catastrophic `VACUUM`-related loss of time-travel history or a Unity Catalog permissions misconfiguration that a metastore-level restore wouldn't fix quickly.
- **Terraform state** stored in a separate, versioned, geo-redundant storage account (not the same account as data) with soft-delete + versioning enabled — infrastructure itself is reproducible from code, but state must survive independently of the environment it describes.
