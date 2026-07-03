resource "azurerm_databricks_workspace" "this" {
  name                        = "dbx-smartmeter-${var.environment}"
  resource_group_name         = var.resource_group_name
  location                    = var.region
  sku                         = var.sku
  managed_resource_group_name = var.managed_resource_group_name

  custom_parameters {
    no_public_ip                                         = var.no_public_ip
    virtual_network_id                                   = var.vnet_id
    public_subnet_name                                   = var.public_subnet_name
    private_subnet_name                                  = var.private_subnet_name
    public_subnet_network_security_group_association_id  = var.public_subnet_nsg_association_id
    private_subnet_network_security_group_association_id = var.private_subnet_nsg_association_id
  }

  # Unity Catalog is enabled by metastore *assignment* (unity-catalog module),
  # not a workspace-level flag — Premium SKU + this workspace resource are
  # the only prerequisites this module owns.

  tags = var.tags
}
