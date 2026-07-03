output "warehouse_id" {
  description = "ID of the SQL Warehouse."
  value       = databricks_sql_endpoint.this.id
}

output "jdbc_url" {
  description = "JDBC connection URL, consumed by Power BI / BI tooling configuration."
  value       = databricks_sql_endpoint.this.jdbc_url
}

output "odbc_params" {
  description = "ODBC connection parameters map, for tools that need discrete host/http-path/port rather than a JDBC URL."
  value       = databricks_sql_endpoint.this.odbc_params
}
