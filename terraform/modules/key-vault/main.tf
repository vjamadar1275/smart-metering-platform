data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                = "kv-smtr-${var.environment}-${substr(md5("${var.environment}-${var.region}"), 0, 6)}"
  resource_group_name = var.resource_group_name
  location            = var.region
  tenant_id           = var.tenant_id
  sku_name            = var.sku_name

  rbac_authorization_enabled = true
  purge_protection_enabled   = var.purge_protection_enabled
  soft_delete_retention_days = var.soft_delete_retention_days

  public_network_access_enabled = var.private_endpoint_subnet_id != null ? false : true

  network_acls {
    default_action = var.private_endpoint_subnet_id != null ? "Deny" : "Allow"
    bypass         = "AzureServices"
  }

  tags = var.tags
}

# Key Vault names must be globally unique across Azure; a short deterministic
# hash of environment+region keeps the name stable across plans without
# requiring a manually-chosen unique suffix.

resource "azurerm_role_assignment" "authorized" {
  for_each = var.authorized_principals

  scope                = azurerm_key_vault.this.id
  role_definition_name = each.value.role
  principal_id         = each.value.principal_id
}

resource "azurerm_role_assignment" "deployer" {
  # The identity running `terraform apply` needs its own access grant — RBAC
  # authorization (unlike legacy access policies) does not implicitly grant
  # the vault creator any data-plane permissions.
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_private_endpoint" "this" {
  count = var.private_endpoint_subnet_id != null ? 1 : 0

  name                = "pe-${azurerm_key_vault.this.name}"
  resource_group_name = var.resource_group_name
  location            = var.region
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${azurerm_key_vault.this.name}"
    private_connection_resource_id = azurerm_key_vault.this.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  dynamic "private_dns_zone_group" {
    for_each = var.private_dns_zone_id != null ? [1] : []
    content {
      name                 = "default"
      private_dns_zone_ids = [var.private_dns_zone_id]
    }
  }

  tags = var.tags
}
