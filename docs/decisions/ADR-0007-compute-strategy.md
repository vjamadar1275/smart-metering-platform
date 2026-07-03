# ADR-0007: Serverless-First Compute, Job Clusters for Scheduled ETL, No All-Purpose in Production

## Status
Accepted

## Context
The platform runs three distinct compute shapes: continuous streaming (Bronze ingestion), scheduled batch/incremental ETL (Silver/Gold pipelines, running on fixed or triggered schedules), and interactive/bursty query workloads (SQL Warehouses, ad hoc notebook development). Cost efficiency at billions-of-records scale requires matching compute lifecycle to workload shape rather than defaulting to always-on infrastructure.

## Decision

| Workload | Compute | Lifecycle |
|---|---|---|
| Bronze/Silver/Gold pipelines (Lakeflow) | **Job Clusters** (Lakeflow-managed) | Ephemeral per pipeline update; autoscale within the run; torn down after |
| SQL (BI, ad hoc, executive) | **Serverless SQL Warehouses** | Auto-start on query, auto-stop after idle timeout |
| Model Serving (Mosaic AI) | **Serverless Model Serving endpoints** | Auto-scale to zero when unused (non-latency-critical models); minimum provisioned concurrency only for models backing real-time alerts |
| Interactive development (notebooks) | **Serverless compute** (dev/staging) or small autoscaling All-Purpose clusters (only where Serverless doesn't yet support a required library/init-script need) | Auto-terminate after idle timeout (e.g. 30–60 min) |
| Production scheduled jobs | **Job Clusters only** — All-Purpose clusters are excluded from production by cluster policy | N/A — never persistent |

## Rationale

- **No All-Purpose clusters in production**: All-Purpose clusters are priced and designed for interactive, multi-user development sessions, not unattended scheduled ETL — running production pipelines on them means paying for a persistent, larger-than-necessary cluster whether or not a job is currently running, and it entangles production workload cost/failure isolation with whatever else happens to be attached to that cluster. Job Clusters are cheaper per DBU for the same work, spin up scoped exactly to one job, and their failure/restart is isolated to that job.
- **Serverless-first for SQL and Model Serving**: at this platform's usage pattern — BI refreshes on a schedule, ad hoc queries bursty during business hours, executive dashboards needing to always feel instant — classic (always-on) compute would need to be sized for peak and left idle most of the time, or manually scheduled to start/stop (itself an operational burden and a source of "dashboard was slow because the warehouse hadn't started yet" incidents). Serverless removes both the idle-cost and the cold-start-timing problems.
- **Photon enabled everywhere it's supported**: Photon's per-DBU premium is consistently outweighed at this data volume by the reduction in cluster-seconds needed for the same Parquet/Delta-heavy, aggregation-heavy workload — validated further in Phase 5/6 with actual benchmark numbers once Gold pipelines are implemented (see [Performance Guide](../guides/), added Phase 8).

## Consequences

- Cluster policies (Phase 2 Terraform) must actively *prevent* All-Purpose cluster creation for production job workloads, not just recommend against it — policy enforcement, not convention, given how easy it is to accidentally attach a production job to a convenient existing All-Purpose cluster.
- Cold-start latency for Job Clusters (a few minutes) is acceptable for scheduled/streaming pipelines but would not be acceptable for interactive BI — this is precisely why SQL Warehouses (Serverless, sub-second-to-seconds autoscale) and Job Clusters are not interchangeable in this platform, despite both being "ephemeral."
- Serverless availability varies by Azure region and feature (e.g. Serverless GPU Model Serving); the Terraform region choice (East US 2 primary) was cross-checked against Serverless feature availability as part of this decision, and must be re-validated if the primary region ever changes.
