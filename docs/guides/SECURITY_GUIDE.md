# Security Guide

Operational procedures for the controls [security-diagram.md](../architecture/diagrams/security-diagram.md) documents architecturally. See that diagram for the *design*; this guide is the *procedure*.

## Key / secret rotation

- **Event Hubs connection string** (`azurerm_key_vault_secret.connection_string`, `terraform/modules/event-hub/main.tf`): rotate via `az eventhubs namespace authorization-rule keys renew`, then `terraform apply` to update the Key Vault secret version — Databricks secret scopes backed by Key Vault (not native scopes, per `databricks_secret_scope`'s `keyvault_metadata` block in each environment's `main.tf`) pick up the new version automatically on next read, no redeploy needed.
- **CI/CD service principal credentials** (`ARM_CLIENT_SECRET`, GitHub Actions secrets): rotate in Entra ID, update the GitHub repo/environment secret immediately after — there is a window where the old secret is invalid and the new one isn't yet configured; coordinate rotation during a low-deploy-frequency period.
- **Databricks PATs used by CI** (`DEV_DATABRICKS_TOKEN`/`STAGING_DATABRICKS_TOKEN`/`PROD_DATABRICKS_TOKEN`): prefer OAuth machine-to-machine (service principal) tokens over long-lived PATs where the Databricks CLI version in `bundle-deploy.yml` supports it; if using PATs, set an expiration and rotate before it lapses, not after `bundle-deploy.yml` starts failing.

## Access reviews

- **SQL Warehouse groups** (`sql_warehouse_bi_group_names`/`_adhoc_group_names`/`_executive_group_names`, `terraform/environments/<env>/variables.tf`): review quarterly — `sqlw-executive`'s narrow group is the one most likely to accumulate stale membership as org structure changes; `sqlw-adhoc`'s broad analyst group is the one most likely to be over-scoped by default (review whether every member still needs ad hoc Silver access, not just Gold).
- **PII mask / row-filter group membership** (`smartmeter-pii-readers`, `smartmeter-analysts-<zone>`, `sql/governance/pii_masking_and_row_filters.sql`): review who can see unmasked `reference.dim_customer.account_name`/`service_address` — this should be a small, named group with a documented business justification per member (billing, customer support), not a role everyone with `sqlw-adhoc` access inherits.
- **Unity Catalog grants**: `sql/governance/pii_masking_and_row_filters.sql`'s baseline GRANT statements are a starting point — audit actual grants periodically via `SHOW GRANTS ON CATALOG <catalog>` / `SHOW GRANTS ON SCHEMA <schema>` against a live workspace, since grants can drift from this reference script after manual admin changes.

## Incident response

See [runbooks/incident-response.md](../runbooks/incident-response.md) for the step-by-step procedure. Summary of severities:

| Severity | Example | Response |
|---|---|---|
| SEV1 | Confirmed unauthorized access to PII, active data exfiltration | Immediate: revoke the compromised principal's access, page platform lead, begin the incident-response runbook. |
| SEV2 | Pipeline failure causing data-quality degradation (elevated quarantine rate), non-PII | Standard on-call triage (Operations Guide), no security escalation unless root cause turns out to be an access-control gap. |
| SEV3 | Access review finds a stale/over-scoped grant, no evidence of misuse | Remediate the grant, log the finding, no incident declared. |

## Compliance evidence

- **Audit trail**: `system.access.audit` (see `sql/observability/audit_log_summary.sql`) + Azure Activity Logs, centralized in the environment's Log Analytics workspace (`terraform/modules/monitoring`) at the retention period set per environment (`log_retention_days`: dev 30 / staging 90 / prod 365 days) — prod's 365-day retention is sized for typical utility-sector regulatory evidence windows; confirm against your actual regulator's requirement before relying on it as sufficient.
- **Lineage**: Unity Catalog's automatic column-level lineage (no manual tagging required) covers "where did this Gold number come from" audit questions — accessible via the workspace's Catalog Explorer lineage tab or `system.lineage.*` system tables.
- **Data classification tags**: `data_classification` in `local.standard_tags` (every environment's `main.tf`) is `"internal"` for dev/staging, `"restricted"` for prod (prod carries regulated/PII customer data) — this tag is what a compliance report would filter environments by, not a per-table tag (per-table PII marking is the masking/row-filter mechanism itself, `sql/governance/`).

## Known open items (not yet closed)

- Real Vector Search / Model Serving endpoint access control (who can call the NL agent, what it's allowed to surface) is scoped by the same Unity Catalog grants as the underlying `gold`/`reference` tables it queries (ADR-0012's `validate_readonly_query`), but a dedicated review of the deployed Model Serving endpoint's own access policy (`bundles/model_serving.yml`) hasn't been done against a live workspace — do this before granting broad access to the NL agent.
- Customer-managed keys (CMK) for ADLS/Databricks DBFS root encryption are named in security-diagram.md's design but not yet wired into `terraform/modules/storage`/`databricks-workspace` — tracked as a follow-up, not implemented in this repository yet.
