# Runbooks

Step-by-step operational procedures for incidents — as opposed to [docs/guides/](../guides/), which cover day-to-day/routine operations. Use a runbook when something has gone seriously wrong (a security incident, a regional outage); use the guides for restarts, backfills, and routine troubleshooting.

| Runbook | Use when |
|---|---|
| [incident-response.md](incident-response.md) | A security incident (unauthorized access, data exfiltration) or a major operational incident (extended outage, data-quality failure affecting a business decision). |
| [dr-failover.md](dr-failover.md) | A confirmed regional outage of the primary Azure region — executes the failover sequence [disaster-recovery-diagram.md](../architecture/diagrams/disaster-recovery-diagram.md) documents architecturally. |

Both runbooks are added in Phase 8, alongside the monitoring/alerting infrastructure (`terraform/modules/monitoring`) and CI/CD (`.github/workflows/`) that would actually trigger their use.
