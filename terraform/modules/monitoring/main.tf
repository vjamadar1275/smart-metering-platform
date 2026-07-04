# Log Analytics Workspace + diagnostic settings + a shared alert action
# group and baseline alert rules. Feeds Lakehouse Monitoring / system-table
# observability (see docs/architecture/diagrams/security-diagram.md's
# Audit & Compliance layer) with a durable, centralized sink independent of
# any single workload's own retention.

resource "azurerm_log_analytics_workspace" "this" {
  name                = "law-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region
  sku                 = var.log_analytics_sku
  retention_in_days   = var.retention_days
  tags                = var.tags
}

# One diagnostic setting per monitored resource (Databricks workspace,
# Event Hubs namespace, storage account, Key Vault, ...) — a single
# diagnostic setting cannot fan out to arbitrarily many resource IDs, so
# this is a for_each over the caller-supplied list, not a single resource.
resource "azurerm_monitor_diagnostic_setting" "this" {
  for_each = toset(var.diagnostic_target_resource_ids)

  name                       = "diag-smartmeter-${var.environment}"
  target_resource_id         = each.value
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  # "Dedicated" routes each log category into its own resource-specific
  # table (e.g. Databricks' DatabricksJobs, DatabricksClusters) rather than
  # the shared, harder-to-query AzureDiagnostics table — required for the
  # `pipeline_failures` alert query below to target DatabricksJobs directly.
  log_analytics_destination_type = "Dedicated"

  # `enabled_log` with `category_group = "allLogs"` is the current
  # (non-deprecated) azurerm provider pattern for "send every log category
  # this resource type exposes" without needing to enumerate them (which
  # differ per resource type and would make this module resource-type-aware).
  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_action_group" "this" {
  name                = "ag-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  short_name          = substr("smtr${var.environment}", 0, 12) # Azure caps short_name at 12 chars

  dynamic "email_receiver" {
    for_each = var.alert_action_group_email_receivers
    content {
      name          = email_receiver.key
      email_address = email_receiver.value
    }
  }

  tags = var.tags
}

# Baseline alert: any Lakeflow pipeline (Bronze/Silver/Gold) or Databricks
# Job failure, surfaced via the Databricks workspace's own diagnostic logs
# once flowing into this Log Analytics workspace. Pipeline/job-specific
# alerting (e.g. streaming lag thresholds) is layered on top of this in
# each pipeline's own `notifications:`/`email_notifications:` block
# (bundles/*.yml) — this is the platform-wide catch-all, not a replacement
# for those.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "pipeline_failures" {
  name                 = "alert-smartmeter-${var.environment}-pipeline-failures"
  resource_group_name  = var.resource_group_name
  location             = var.region
  severity             = 1
  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  scopes               = [azurerm_log_analytics_workspace.this.id]

  criteria {
    query                   = <<-QUERY
      DatabricksJobs
      | where ActionName == "runFailed" or ActionName == "runFailedWithTimeout"
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }

  tags = var.tags
}
