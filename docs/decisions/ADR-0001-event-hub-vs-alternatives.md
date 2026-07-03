# ADR-0001: Azure Event Hubs (Dedicated Tier) for Telemetry Ingestion

## Status
Accepted

## Context
The platform must durably ingest telemetry from 10M meters today (≈11K events/sec average, ≈44K peak) scaling to 100M meters (≈111K average, ≈444K peak), with zero data loss and native, low-friction integration into Azure Databricks Structured Streaming.

Options considered:

1. **Azure Event Hubs** (Standard or Dedicated tier)
2. **Azure IoT Hub**
3. **Self-managed Apache Kafka** (on AKS or HDInsight)
4. **Confluent Cloud (Kafka-as-a-service) on Azure**

## Decision
Use **Azure Event Hubs, Dedicated tier**, with the Kafka-compatible endpoint available as a fallback integration surface if a future component requires native Kafka protocol.

## Rationale

- **vs. IoT Hub**: IoT Hub is purpose-built for device *management* (twin state, device provisioning, C2D commands) which this platform doesn't need — meters are dumb telemetry publishers, not managed IoT Hub devices. IoT Hub's throughput ceiling (per-unit and per-hub) and per-message pricing model are also less favorable at this event volume than Event Hubs' throughput-unit/capacity-unit model. If device provisioning/management needs emerge later, Azure Device Provisioning Service can be added independently without changing the ingestion broker.
- **vs. self-managed Kafka**: eliminates cluster operations (broker patching, partition rebalancing, ZooKeeper/KRaft management, scaling operations) entirely. At this event volume, a self-managed cluster would need dedicated SRE ownership; Event Hubs Dedicated gives predictable, isolated throughput (Capacity Units, not noisy-neighbor Throughput Units) with a Microsoft SLA.
- **vs. Confluent Cloud**: keeps the ingestion broker inside the Azure trust boundary — Private Link to Event Hubs is a first-party, well-trodden path into Databricks; Confluent Cloud on Azure requires either public endpoints or Azure PrivateLink to a third-party-managed control plane, adding a second vendor to the security/compliance review surface for marginal benefit given Databricks' first-party Event Hubs connector.
- **Dedicated over Standard tier from day one**: Standard tier caps at 40 Throughput Units (~40K events/sec or 40MB/s). That's already close to our 10M-meter peak (44K events/sec) with zero headroom, and an order of magnitude short of the 100M-meter target. Dedicated tier's Capacity Units scale further and provide single-tenant infrastructure (predictable latency, longer retention up to 90 days — valuable for replay during extended Databricks-side incidents).

## Consequences

- Higher fixed cost floor than Standard tier (Dedicated is billed per Capacity Unit-hour regardless of load) — accepted because Standard's ceiling is inadequate for the design target and CU cost is justified by removing an entire class of future migration risk.
- Geo-Disaster Recovery (alias-based failover) is a Dedicated/Standard feature we depend on for the DR strategy — see [disaster-recovery-diagram.md](../architecture/diagrams/disaster-recovery-diagram.md).
- Partition count (200, growing toward 800+) is fixed at creation time per Event Hub in practical terms (increasing later reshuffles key→partition mapping); we deliberately over-provision partitions relative to current 10M-meter needs to avoid a disruptive migration at 100M-meter scale.
