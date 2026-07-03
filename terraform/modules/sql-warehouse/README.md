# Module: sql-warehouse

Provisions the workload-isolated Serverless SQL Warehouses (`sqlw-bi`, `sqlw-adhoc`, `sqlw-executive`) defined in [ADR-0005](../../../docs/decisions/ADR-0005-sql-warehouse-isolation.md). One module instance per warehouse, called three times from the environment root module (Phase 6).

**Status**: interface defined (Phase 1); resources implemented in Phase 6.
