# One Serverless SQL Warehouse per module instance, called three times
# (bi/adhoc/executive) from each environment root module — see ADR-0005.

resource "databricks_sql_endpoint" "this" {
  provider = databricks.workspace

  name             = "${var.warehouse_name}-${var.environment}"
  cluster_size     = var.cluster_size
  min_num_clusters = var.min_clusters
  max_num_clusters = var.max_clusters

  auto_stop_mins            = var.auto_stop_minutes
  enable_serverless_compute = var.enable_serverless
  warehouse_type            = "PRO" # required for enable_serverless_compute
  spot_instance_policy      = "COST_OPTIMIZED"
  enable_photon             = var.enable_photon

  tags {
    custom_tags {
      key   = "purpose"
      value = var.warehouse_purpose
    }
    dynamic "custom_tags" {
      for_each = var.tags
      content {
        key   = custom_tags.key
        value = custom_tags.value
      }
    }
  }
}

# CAN_USE per ADR-0005's access-scoping intent (e.g. sqlw-executive granted
# to a small named group, sqlw-adhoc to all analysts) — one permissions
# resource per authorized group, group membership/creation itself is owned
# outside this module (Entra ID / account-console group sync, per
# terraform/README.md's identity-boundary conventions).
resource "databricks_permissions" "this" {
  provider = databricks.workspace

  sql_endpoint_id = databricks_sql_endpoint.this.id

  dynamic "access_control" {
    for_each = var.authorized_group_names
    content {
      group_name       = access_control.value
      permission_level = "CAN_USE"
    }
  }
}
