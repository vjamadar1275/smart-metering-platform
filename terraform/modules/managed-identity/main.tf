resource "azurerm_user_assigned_identity" "this" {
  for_each = toset(var.identities)

  name                = "id-smartmeter-${var.environment}-${each.value}"
  resource_group_name = var.resource_group_name
  location            = var.region
  tags                = var.tags
}
