-- System-table-based SQL Warehouse performance observability (Phase 8) —
-- reference query over system.query.history, scoped to this platform's
-- three workload-isolated warehouses (ADR-0005). Useful for validating
-- ADR-0005's premise directly: are sqlw-bi/sqlw-executive queries staying
-- fast regardless of what sqlw-adhoc is doing concurrently?

SELECT
    warehouse_id,
    date_trunc('hour', start_time) AS query_hour,
    count(*) AS query_count,
    avg(total_duration_ms) AS avg_duration_ms,
    percentile(total_duration_ms, 0.95) AS p95_duration_ms,
    sum(CASE WHEN execution_status = 'FAILED' THEN 1 ELSE 0 END) AS failed_query_count
FROM system.query.history
WHERE
    start_time >= current_timestamp() - INTERVAL 7 DAYS
    -- Replace with the real warehouse IDs from
    -- `terraform output sql_warehouse_ids` (terraform/environments/<env>) —
    -- system.query.history has no direct tag/project column to filter by,
    -- unlike system.billing.usage.
    AND warehouse_id IN ('REPLACE-WITH-SQLW-BI-ID', 'REPLACE-WITH-SQLW-ADHOC-ID', 'REPLACE-WITH-SQLW-EXECUTIVE-ID')
GROUP BY ALL
ORDER BY query_hour DESC, warehouse_id;
