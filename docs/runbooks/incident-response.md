# Runbook: Incident Response

For security incidents (SEV1/SEV2 per [SECURITY_GUIDE.md](../guides/SECURITY_GUIDE.md)'s severity table) and major operational incidents (extended pipeline outage, data-quality failure affecting a business decision). For routine pipeline failures, use [OPERATIONS_GUIDE.md](../guides/OPERATIONS_GUIDE.md) and [TROUBLESHOOTING_GUIDE.md](../guides/TROUBLESHOOTING_GUIDE.md) instead — this runbook is for incidents, not routine triage.

## 1. Detect and classify

Sources: `terraform/modules/monitoring`'s alert action group (pipeline/job failures), `sql/observability/audit_log_summary.sql` (anomalous access patterns), a direct report (customer/regulator/internal). Classify severity per the Security Guide's table before proceeding — this determines who gets paged and how fast.

## 2. Contain (SEV1 — active unauthorized access / data exfiltration)

1. **Revoke the compromised principal's access immediately**: `REVOKE ALL PRIVILEGES ON CATALOG <catalog> FROM <principal>` (Unity Catalog), or disable the Entra ID account/service principal entirely if the compromise is broader than one grant.
2. **Rotate any credential the principal may have had access to** — Key Vault secrets (Event Hubs connection string), Databricks PATs, service principal secrets. See [SECURITY_GUIDE.md](../guides/SECURITY_GUIDE.md)'s rotation procedures.
3. **Do not** delete audit logs, quarantine data, or Silver/Gold tables the incident might involve — they're the evidence. Time Travel / deep clones (see disaster-recovery-diagram.md's Backup Strategy) protect against an incident *response* action accidentally destroying evidence.

## 3. Investigate

- `system.access.audit` (`sql/observability/audit_log_summary.sql`) — what did the compromised/anomalous principal actually access, and when.
- Unity Catalog lineage (Catalog Explorer, or `system.lineage.*`) — did anything downstream of an affected table get built from compromised/incorrect data.
- `quarantine.silver_meter_readings` / pipeline event logs — for a data-quality incident, establish the blast radius (which `reading_date`/`dma_id`/`customer_id` ranges are affected) before deciding on remediation.

## 4. Remediate

- **PII exposure**: confirm `sql/governance/pii_masking_and_row_filters.sql`'s masking/row-filter functions are actually applied (`SHOW GRANTS`, `DESCRIBE TABLE EXTENDED reference.dim_customer` to check `SET MASK` is in effect) — a masking gap is itself a root cause worth fixing, not just the immediate access.
- **Data-quality incident**: reprocess the affected Bronze/Silver range once the root cause (schema drift, a reference-data gap, a pipeline bug) is fixed — see Operations Guide's Backfills section.
- **Infrastructure compromise**: rotate every credential the affected resource group's managed identities had access to, not just the one directly implicated — lateral movement is a real risk per the Security Control Matrix.

## 5. Communicate

- Internal: platform lead + affected team leads, with a running timeline (detect time, contain time, root cause, remediation).
- External (regulatory/customer): follow your organization's breach-notification policy and timeline requirements — this repository does not define that policy; it's organization- and jurisdiction-specific (water-utility regulatory regimes vary).

## 6. Post-incident

- Write up: what happened, detection time, containment time, root cause, what's changed to prevent recurrence.
- If the root cause was a gap in this platform's controls (a missing mask, an over-broad grant, a missing alert), fix it and note the fix in the relevant guide/ADR — an incident that doesn't change the system is one that will recur.
- Update [SECURITY_GUIDE.md](../guides/SECURITY_GUIDE.md)'s "Known open items" section if the incident surfaced a gap not yet on that list.
