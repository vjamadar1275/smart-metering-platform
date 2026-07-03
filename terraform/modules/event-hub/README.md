# Module: event-hub

Provisions the Event Hubs Dedicated-tier namespace, the `meter-telemetry` hub (200+ partitions), consumer groups (Bronze streaming, anomaly-detection streaming, monitoring), Schema Registry, and Geo-DR pairing, per [ADR-0001](../../../docs/decisions/ADR-0001-event-hub-vs-alternatives.md).

**Status**: interface defined (Phase 1); resources implemented in Phase 3 (this module is consumed by the streaming ingestion phase, later than the other infrastructure modules — see [README.md delivery phases](../../../README.md#delivery-phases)).
