# Security Diagram

Layered security model: identity → network → data → application, mapped to Zero Trust principles (verify explicitly, least privilege, assume breach).

```mermaid
flowchart TB
    subgraph Identity["Identity Layer"]
        Entra[Microsoft Entra ID]
        SP[Service Principals / Managed Identities<br/>per workload, no shared credentials]
        Groups[Entra Security Groups<br/>mapped to Unity Catalog grants]
        PIM[Entra PIM<br/>just-in-time elevation for admin roles]
    end

    subgraph NetworkSec["Network Layer"]
        PL[Private Link<br/>ADLS / Event Hub / Key Vault / Databricks]
        FW[Azure Firewall<br/>egress allow-listing]
        NSGRules[NSGs<br/>deny-by-default]
    end

    subgraph SecretsLayer["Secrets & Key Management"]
        KV[Azure Key Vault<br/>Premium, HSM-backed]
        CMK[Customer-Managed Keys<br/>ADLS + Databricks DBFS root encryption]
        DBXSecrets[Databricks Secret Scopes<br/>backed by Key Vault, not native]
    end

    subgraph DataSec["Data Layer"]
        EncRest[Encryption at Rest<br/>AES-256, CMK via Key Vault]
        EncTransit[Encryption in Transit<br/>TLS 1.2+ everywhere]
        UCRBAC[Unity Catalog RBAC<br/>catalog/schema/table grants]
        UCABAC[Unity Catalog ABAC<br/>attribute-based policies, tags]
        RLS[Row-Level Security<br/>row filters, e.g. by DMA/region]
        CM[Column Masking<br/>PII: customer name, address, account no.]
        Lineage[Data Lineage<br/>automatic, column-level]
    end

    subgraph AuditLayer["Audit & Compliance"]
        AuditLogs[Unity Catalog Audit Logs<br/>+ Azure Activity Logs]
        SysTables[System Tables<br/>access, billing, lineage, query history]
        LAW[Log Analytics Workspace<br/>centralized SIEM sink]
        Compliance[Compliance Reporting<br/>SOC2 / ISO27001 / regional water-utility regs]
    end

    Entra --> SP --> Groups --> UCRBAC
    PIM -.gates.-> Groups
    UCRBAC --> UCABAC --> RLS
    UCABAC --> CM
    KV --> CMK --> EncRest
    KV --> DBXSecrets
    PL --> EncTransit
    NSGRules --> PL

    UCRBAC -.every access.-> AuditLogs
    RLS -.every access.-> AuditLogs
    CM -.every access.-> AuditLogs
    AuditLogs --> SysTables --> LAW --> Compliance
    Lineage --> SysTables
```

## Security Control Matrix

| Threat | Control |
|---|---|
| Credential theft / shared secrets | Managed Identities + Service Principals per workload; no embedded connection strings; Key Vault-backed Databricks secret scopes |
| Lateral movement via network | Private Link everywhere, deny-by-default NSGs, Azure Firewall egress allow-listing |
| Data exfiltration | Private endpoints (no public data-plane path), Unity Catalog governs even ad hoc SQL access, egress FQDN allow-listing prevents arbitrary outbound |
| Unauthorized PII access | Column masking (customer PII) + row-level security (DMA/region scoping) enforced at the Unity Catalog layer, not per-application |
| Privilege creep | Entra PIM just-in-time elevation for workspace/catalog admin roles; standing access is read-scoped by default |
| Undetected access / tampering | Unity Catalog audit logs + system tables, centralized in Log Analytics with alerting on anomalous access patterns |
| Data at rest exposure | AES-256 encryption, customer-managed keys via Key Vault (meets utility-sector data sovereignty requirements) |
| Data in transit exposure | TLS 1.2+ enforced on every hop, including field gateway → Event Hub |

See [ADR set](../decisions/) for the reasoning behind each governance choice, and the (Phase 8) Security Guide for operational procedures (key rotation, access reviews, incident response).
