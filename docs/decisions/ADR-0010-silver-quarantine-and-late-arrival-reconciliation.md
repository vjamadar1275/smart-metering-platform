# ADR-0010: Reason-Coded Quarantine (Not Drop) + Batch Late-Arrival Reconciliation Outside Lakeflow

## Status
Accepted

## Context

Phase 4 (Silver) must satisfy two related but distinct requirements from `docs/architecture/ARCHITECTURE.md#3-bronze--silver`:

1. Rows that fail validation must be quarantined with a reason code, never silently dropped.
2. A reading arriving more than the streaming watermark (24h) after event-time already seen must still land in Silver eventually, via "a nightly batch reconciliation pass."

Both requirements collide with the same underlying constraint: Lakeflow's native tools for each — `expect_all_or_drop`/`expect_all_or_fail` for validation, and `apply_changes`'s watermarked stateful dedup for redelivery collapse — are built around *acting on* a violation (drop the row, fail the pipeline, expire old state), not *preserving it with context* for later handling.

### Decision 1: Quarantine reason codes as data, not Lakeflow Expectations metrics

Options considered:

1. **`dp.expect_all_or_drop`** with named boolean expectations — Lakeflow tracks per-rule pass/fail counts as pipeline metrics automatically, but a row that fails is *dropped*, full stop; there's no hook to instead route it elsewhere with a reason attached.
2. **`dp.expect_all`** (metrics-only, never drops) alone — rows always continue downstream regardless of validity, which would let invalid data reach `silver.meter_readings` even though metrics would show the violation. Unacceptable: Silver's whole purpose is being a trustworthy single source of truth.
3. **Reason codes computed as a plain column** (`quarantine_reasons: array<string>`, this ADR's choice), with `dp.expect_all` used *additionally* for genuinely non-blocking metric-only rules (battery/signal range) where Lakeflow's built-in metrics are sufficient and no reason-code/quarantine routing is needed.

**Decision**: Hard (quarantine-triggering) rules are evaluated as an explicit column (`src/libs/quality/expectations.py:with_quarantine_reasons`), and the resulting `is_valid` flag splits the stream into `silver.meter_readings` (apply_changes target) and `quarantine.silver_meter_readings_quarantine` (append-only, with reason codes) as two separate Lakeflow flows reading the same upstream view. Soft rules (battery/signal — informational, never actionable at row level) use `dp.expect_all` for its free metrics, since there's nothing to route or preserve beyond the metric itself.

**Rationale**: This is a small amount of extra code (one function, tested in `tests/unit/test_quality_expectations.py`) in exchange for the actual requirement — a queryable, reason-coded quarantine table an operator can `SELECT reason, COUNT(*) FROM quarantine.silver_meter_readings_quarantine GROUP BY explode(quarantine_reasons)` against — which neither `expect_all_or_drop` nor `expect_all` alone can produce. The cost is that these rules aren't visible in Lakeflow's built-in expectations UI/metrics the way `expect_all`-tracked rules are; this is an accepted gap, revisited if Lakeflow adds a native "quarantine" expectation action in a future Databricks Runtime release.

### Decision 2: Late-arrival reconciliation as a separate batch Job, not a second Lakeflow flow

Options considered:

1. **Widen the watermark** (e.g. 7 days instead of 24h) so more late arrivals are naturally absorbed by the same streaming `apply_changes`. Rejected: watermark state size is proportional to the window times the per-meter cardinality (10M meters today, 100M at design target) — a 7-day watermark holds ~7x the deduplication state permanently in every streaming micro-batch, for a case (multi-day connectivity outage) that ADR's own architecture doc describes as the exception, not the norm. This is a permanent tax on the common case to cover a rare one.
2. **A second Lakeflow flow into the same `apply_changes` target**, reading Bronze without a watermark (or a much larger one) on a triggered/batch cadence. Lakeflow's current `apply_changes` model is built around one logical CDC source per target; layering a second, differently-triggered flow with overlapping keys into the same MERGE target is unsupported by the framework as a first-class pattern and would require working against its grain.
3. **A plain batch Spark job, run nightly as a nothing-fancy nightly Databricks Job task, that re-derives validity for the last few days of Bronze and idempotently `MERGE`s into `silver.meter_readings`/`quarantine.silver_meter_readings_quarantine`** (this ADR's choice; `src/jobs/silver_late_arrival_reconciliation.py`).

**Decision**: Option 3. The streaming flow's 24h watermark stays tight (bounded state, fast dedup for the 99%+ common case), and a separate, idempotent, nightly batch job — deliberately *not* a Lakeflow pipeline, per ADR-0003's own carve-out for "genuinely imperative logic" — sweeps a `--lookback-days` (default 3, must exceed the watermark) window of Bronze and reconciles anything the streaming flow's watermark dropped. It reuses the exact same enrichment/validation code (`src/libs/quality/expectations.py`, `src/libs/common/units.py`) as the streaming path, so a late-arriving record is judged identically to an on-time one.

**Rationale**: This isolates a rare-but-real correctness requirement (zero data loss, per the platform's own non-negotiable requirement) into code that runs on a schedule matched to the actual arrival pattern of late data (nightly is more than sufficient for a case measured in hours-to-days) rather than distorting the streaming path's state size for it. It costs a second deployable artifact (a plain Databricks Job, per ADR-0007's "scheduled ETL → Job Clusters" row) and the discipline of keeping its validation logic in sync with the streaming path's — mitigated by both paths calling the same shared library functions rather than each having their own copy of the rules.

## Consequences

- `src/libs/quality/expectations.py` and `src/libs/common/units.py` are now load-bearing shared code for *two* execution paths (the Lakeflow pipeline and the batch job) — any future rule change updates both automatically, but also means neither path can be tested purely in isolation from the other's behavior; `tests/unit/` tests the shared functions directly rather than either integration.
- The reconciliation job's `--lookback-days` must always exceed `--watermark-hours / 24`, checked at runtime (`src/jobs/silver_late_arrival_reconciliation.py:run`) — a misconfiguration that narrows the window below the watermark would silently create the exact gap this job exists to close, so it fails loudly instead.
- A reading arriving *later* than `lookback_days` past the streaming watermark (e.g. a meter offline for over a week in the default config) is still not reconciled automatically; closing that residual gap further would mean either a longer lookback (bounded reprocessing cost, tune per observed field connectivity data) or an operator-triggered ad hoc run — both are operationally acceptable and documented as an open tuning item for Phase 8's Operations Guide rather than solved further here, since the actual field connectivity-gap distribution needed to size this correctly doesn't exist yet (this repository has no production traffic).
- `databricks bundle validate` could not be executed against these changes in this sandboxed environment — the Databricks CLI is a compiled binary distributed only via GitHub Releases, and this environment's network policy blocks direct GitHub Releases downloads (pip/PyPI-hosted tooling is allowed; this is not). `bundles/silver_pipeline.yml` and `bundles/silver_late_arrival_reconciliation_job.yml` were instead checked for YAML syntax validity and hand-verified against the same resource shapes as the already-deployed `bundles/bronze_pipeline.yml`. Running `databricks bundle validate -t dev` in an environment with CLI access is a follow-up item before any real deploy.
