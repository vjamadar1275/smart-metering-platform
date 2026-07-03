# Module: event-hub

Provisions the Event Hubs namespace (optionally backed by a Dedicated cluster — see [ADR-0001](../../../docs/decisions/ADR-0001-event-hub-vs-alternatives.md)), the `meter-telemetry` hub (200+ partitions), consumer groups (Bronze streaming, anomaly-detection streaming, monitoring), Schema Registry group, Geo-DR pairing, and a Key Vault secret holding the connection string.

**Status**: implemented (Phase 3).

## Notes

- `use_dedicated_cluster = true` provisions a real `azurerm_eventhub_cluster` (Dedicated tier) — this has a significant fixed cost floor, so it defaults to `false`. Prod and staging enable it at the environment root; dev does not (dev represents a small functional-testing subset of the fleet, not the full 10M-meter throughput ADR-0001 sized Dedicated tier for).
- Individual Avro schema *versions* under `schemas/avro/` are registered into the schema group this module creates via the Schema Registry SDK/API at pipeline-deployment time, not by Terraform — see [docs/decisions/ADR-0009-event-hub-connector-protocol.md](../../../docs/decisions/ADR-0009-event-hub-connector-protocol.md).
