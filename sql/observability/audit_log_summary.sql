-- System-table-based audit observability (Phase 8) — reference query over
-- system.access.audit, the Unity Catalog audit log surfaced as a system
-- table (see security-diagram.md's Audit & Compliance layer:
-- "AuditLogs --> SysTables --> LAW --> Compliance"). Scoped to actions
-- against this environment's catalog, so it can flag e.g. an unexpected
-- spike in denied-access events or PII-column reads outside the
-- smartmeter-pii-readers group (sql/governance/pii_masking_and_row_filters.sql).

SELECT
    date_trunc('day', event_time) AS event_day,
    service_name,
    action_name,
    count(*) AS event_count,
    count(DISTINCT user_identity.email) AS distinct_users
FROM system.access.audit
WHERE
    event_time >= current_timestamp() - INTERVAL 30 DAYS
    -- request_params.full_name_arg / table_full_name vary by action_name;
    -- this LIKE match on the catalog name is a broad first filter — refine
    -- per action_name's actual audit schema once run against a live
    -- workspace (Databricks' audit log schema differs slightly by service).
    AND request_params['full_name_arg'] LIKE 'smartmeter\_%' ESCAPE '\\'
GROUP BY ALL
ORDER BY event_day DESC, event_count DESC;
