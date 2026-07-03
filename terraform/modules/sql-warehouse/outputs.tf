output "warehouse_id" {
  description = "ID of the SQL Warehouse."
  value       = null # populated in Phase 6
}

output "jdbc_url" {
  description = "JDBC connection URL, consumed by Power BI / BI tooling configuration."
  value       = null # populated in Phase 6
}

output "odbc_params" {
  description = "ODBC connection parameters map, for tools that need discrete host/http-path/port rather than a JDBC URL."
  value       = {} # populated in Phase 6
}
