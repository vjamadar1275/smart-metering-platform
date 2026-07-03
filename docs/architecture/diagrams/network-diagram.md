# Network Diagram

All PaaS control-plane traffic and data-plane traffic between Databricks compute and dependent services (ADLS, Event Hubs, Key Vault) is designed to stay off the public internet.

```mermaid
flowchart TB
    subgraph Internet["Public Internet"]
        Dev[Developer / GitHub Actions runner]
        Meter[Field Gateways]
    end

    subgraph AzureAD["Microsoft Entra ID (identity plane)"]
        Entra[Entra ID<br/>SSO, Conditional Access, MFA]
    end

    subgraph VNet["VNet: vnet-smartmeter-prod (10.10.0.0/16)"]
        subgraph SubnetPublic["snet-databricks-public (10.10.1.0/24)"]
            NAT[NAT Gateway<br/>egress-only]
        end

        subgraph SubnetPrivate["snet-databricks-private (10.10.2.0/24)"]
            DBXCompute[Databricks Compute Plane<br/>Job Clusters, SQL Warehouses<br/>Secure Cluster Connectivity: no public IP]
        end

        subgraph SubnetPE["snet-private-endpoints (10.10.3.0/24)"]
            PEADLS[Private Endpoint: ADLS Gen2]
            PEEH[Private Endpoint: Event Hubs]
            PEKV[Private Endpoint: Key Vault]
            PEDBX[Private Endpoint: Databricks control plane]
        end

        subgraph SubnetFW["snet-firewall (10.10.0.0/26)"]
            AzFW[Azure Firewall<br/>egress filtering, FQDN allow-list]
        end

        PrivateDNS[Private DNS Zones<br/>privatelink.*.azure.net/windows.net]
    end

    subgraph PaaS["Azure PaaS (private-linked)"]
        ADLS[(ADLS Gen2)]
        EHNS[(Event Hubs Namespace)]
        KV[(Key Vault)]
        DBXCtrl[Databricks Control Plane<br/>Microsoft-managed]
    end

    Meter -->|AMQP over TLS 1.2+, public endpoint<br/>with IP allow-list + SAS/OAuth| EHNS
    Dev -->|HTTPS, Entra auth| DBXCtrl

    DBXCompute -->|SCC: outbound-only relay, no inbound| DBXCtrl
    DBXCompute --> PEADLS --> ADLS
    DBXCompute --> PEEH --> EHNS
    DBXCompute --> PEKV --> KV
    PEDBX --- DBXCtrl

    DBXCompute -.egress for package installs etc.-> NAT --> AzFW
    AzFW -.allow-listed FQDNs only.-> Internet

    SubnetPE --- PrivateDNS
    Entra -.authenticates.-> DBXCompute
    Entra -.authenticates.-> Dev
```

## Key Network Controls

| Control | Implementation |
|---|---|
| No public IPs on compute | Databricks **Secure Cluster Connectivity (SCC)** — all control-plane communication is outbound-only from the customer VNet |
| No public data-plane access | **Private Endpoints** for ADLS Gen2, Event Hubs, Key Vault, and the Databricks workspace's own front-end; public network access disabled on each resource |
| Egress control | **Azure Firewall** with FQDN allow-listing for package repos (PyPI, Maven Central mirrors) and Databricks/MLflow artifact endpoints; all other egress denied |
| Field ingestion path | Event Hubs public endpoint restricted via **IP firewall rules** to known gateway egress ranges, plus SAS-token/OAuth authentication — evaluated in Phase 8 for migration to a dedicated ingestion path (e.g. ExpressRoute) if gateway IP ranges stabilize |
| Name resolution | **Private DNS Zones** linked to the VNet so private-endpoint FQDNs resolve to private IPs, including from peered dev/staging VNets |
| Environment isolation | Separate VNets per environment (dev/staging/prod), peered only where explicitly required (none, by default) |
