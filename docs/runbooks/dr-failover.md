# Runbook: Disaster Recovery Failover

Executes the failover sequence [disaster-recovery-diagram.md](../architecture/diagrams/disaster-recovery-diagram.md) documents architecturally, for a **regional outage of the primary region** (East US 2). Do not use this runbook for a single-service outage (e.g. just Event Hubs degraded) — diagnose and remediate that service directly first; failing over is itself costly (RTO measured in tens of minutes to hours) and should only be invoked when the primary region itself is confirmed down or unreachable.

## Prerequisites (confirm before starting)

- `enable_dr_region = true` in `terraform/environments/prod/variables.tf` (the secondary-region resource groups must already exist — this runbook does not provision them from scratch).
- Geo-DR pairing for Event Hubs must be enabled (`terraform/environments/prod/main.tf`'s `event_hub` module currently sets `enable_geo_dr = false` — **this must be flipped to `true` and applied before this runbook is usable for real**; the DR failover sequence below assumes it is, per disaster-recovery-diagram.md's design, but this repository has not yet wired that piece up, see that file's own comment).

## Failover sequence

1. **Detect and confirm regional outage.** Azure Monitor / Azure Service Health should corroborate a genuine regional issue, not just this platform's own alerts — a false failover has real cost and risk. Get a second confirming signal (Azure status page, another affected service) before proceeding.
2. **Initiate Event Hubs Geo-DR failover.** `az eventhubs georecovery-alias fail-over --resource-group <rg> --namespace-name <primary-namespace> --alias <geo-dr-alias-name>` (alias name from `terraform output` on the `event_hub` module, or `module.event_hub.geo_dr_alias_name`). Field gateways reconnect using the same alias FQDN — no gateway-side configuration change needed.
3. **Confirm field gateways are reconnecting** to the secondary namespace (Event Hubs portal metrics, or `system.access.audit`-equivalent for Event Hubs if wired into monitoring).
4. **Start standby Structured Streaming jobs** in the secondary-region Databricks workspace — `databricks bundle deploy -t prod` against the secondary workspace's host (this requires the secondary workspace to already have the bundle's resources deployed in a stopped/paused state; confirming that parity is itself a periodic DR-readiness check, not something this runbook establishes for the first time during a real incident).
5. **Validate Unity Catalog metastore attachment** for the secondary workspace — prod owns its own dedicated metastore (ADR-0006); confirm the secondary workspace is correctly assigned before assuming catalog/schema access works.
6. **Re-point SQL Warehouses + Power BI** — update the Power BI semantic model's `Databricks Host`/`Databricks HTTP Path` parameters (`power_bi/SmartMeteringSemanticModel.SemanticModel/definition/expressions.tmdl`) to the secondary workspace's SQL Warehouse endpoints, and republish/refresh.
7. **Resume Gold pipelines + AI serving** — `gold_daily_marts_trigger`, `ml_model_training`, and the `leak_detection_endpoint` Model Serving deployment in the secondary workspace.

## Recovery objectives (reference — see disaster-recovery-diagram.md for the full table)

| Component | RTO |
|---|---|
| Event Hub | < 15 min |
| ADLS Gen2 | < 30 min |
| Streaming pipelines | < 1 hour |
| Unity Catalog metadata | < 30 min |
| BI / AI serving | < 4 hours (lowest priority — depends on pipelines being healthy first) |

## Failback

Not covered by this runbook version — failing back to the primary region once it recovers requires re-establishing Geo-DR pairing in the reverse direction and a second, planned (not emergency) cutover, typically scheduled during a maintenance window rather than executed immediately once the primary region is merely reachable again. Treat failback as a separate, deliberately-planned change, not an automatic reversal of this runbook's steps.

## Open items

- Step 2's Geo-DR failover cannot actually be exercised today — `enable_geo_dr = false` in `terraform/environments/prod/main.tf` (see that file's comment: the secondary-region bare namespace target for Geo-DR replication is provisioned "alongside the rest of the DR failover path in Phase 8, not created piecemeal here"). Enabling and testing real Geo-DR failover is the concrete next step to make this runbook executable rather than descriptive.
- This runbook has never been executed, even in a drill — per this repository's constraint against applying real infrastructure. Once prod is actually applied, schedule a DR drill (a controlled, planned failover test, not a real outage) to validate every step above actually works as written, and correct this document based on what the drill finds.
