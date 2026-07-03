# Deployment Diagram

Physical/Azure resource placement across regions and environments. Primary region: **East US 2**. DR/secondary region: **Central US** (Azure paired region, satisfies data-residency and paired-region SLA guidance).

```mermaid
flowchart TB
    subgraph Primary["Primary Region — East US 2"]
        subgraph RG_Net["rg-smartmeter-network-prod"]
            VNet1[VNet: 10.10.0.0/16]
            PE1[Private Endpoints:<br/>ADLS, Event Hub, Key Vault,<br/>Databricks control plane]
            NSG1[NSGs / Route Tables]
        end

        subgraph RG_Data["rg-smartmeter-data-prod"]
            EH1[Event Hubs Namespace<br/>Dedicated Tier, Geo-DR primary]
            ADLS1[ADLS Gen2<br/>GZRS, hierarchical namespace]
            KV1[Key Vault<br/>Premium, HSM-backed]
        end

        subgraph RG_Databricks["rg-smartmeter-databricks-prod"]
            DBXWS1[Databricks Workspace<br/>VNet-injected, SCC enabled]
            UCMeta[Unity Catalog Metastore<br/>region-level, shared by all workspaces]
            subgraph Compute1["Compute (ephemeral, VNet-injected)"]
                JC1[Job Clusters<br/>Bronze/Silver/Gold pipelines]
                SQLWH1[Serverless SQL Warehouses]
                MLServe1[Model Serving<br/>Serverless GPU/CPU endpoints]
            end
        end

        subgraph RG_Mon["rg-smartmeter-monitoring-prod"]
            LAW1[Log Analytics Workspace]
            AppInsights1[Application Insights]
            AlertRules1[Azure Monitor Alert Rules]
        end
    end

    subgraph Secondary["Secondary Region — Central US (DR, warm standby)"]
        EH2[Event Hubs Namespace<br/>Geo-DR secondary alias]
        ADLS2[ADLS Gen2<br/>GZRS geo-replica, read-only until failover]
        DBXWS2[Databricks Workspace<br/>pre-provisioned, no running compute]
        KV2[Key Vault replica]
    end

    subgraph SharedControl["Shared / Global"]
        AAD[Microsoft Entra ID]
        UCAccount[Unity Catalog Account Console]
        GH[GitHub Actions<br/>CI/CD runners]
    end

    EH1 -.Geo-DR pairing.-> EH2
    ADLS1 -.GZRS async replication.-> ADLS2
    DBXWS1 -.Terraform-mirrored config.-> DBXWS2
    KV1 -.replication.-> KV2

    AAD --> DBXWS1
    AAD --> DBXWS2
    AAD --> ADLS1
    UCAccount --> UCMeta
    GH -->|Databricks Asset Bundles<br/>deploy| DBXWS1
    GH -->|Terraform apply| RG_Net
    GH -->|Terraform apply| RG_Data
    GH -->|Terraform apply| RG_Databricks

    VNet1 --- PE1
    PE1 --- EH1
    PE1 --- ADLS1
    PE1 --- KV1
    DBXWS1 --- Compute1
    Compute1 --> ADLS1
    Compute1 --> EH1
    Compute1 --> KV1
    LAW1 --- DBXWS1
    LAW1 --- EH1
```

## Environment Topology

| Environment | Resource groups | Databricks workspace | Unity Catalog metastore | Notes |
|---|---|---|---|---|
| dev | `rg-smartmeter-*-dev` | `dbx-smartmeter-dev` | Shared dev/staging metastore (region-level) | Smaller SKUs, shorter Event Hub retention |
| staging | `rg-smartmeter-*-staging` | `dbx-smartmeter-staging` | Shared dev/staging metastore | Production-shaped, production-scale-down data |
| prod | `rg-smartmeter-*-prod` (+ secondary region) | `dbx-smartmeter-prod` | Dedicated prod metastore | Full HA/DR, Dedicated Event Hub tier |

One Unity Catalog **metastore per region**, attached to all workspaces in that environment tier — not one per workspace — per Databricks' recommended account topology (see [ADR-0006](../decisions/ADR-0006-unity-catalog-strategy.md)).
