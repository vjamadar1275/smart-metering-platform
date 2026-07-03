resource "azurerm_virtual_network" "this" {
  name                = "vnet-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region
  address_space       = var.vnet_address_space
  tags                = var.tags
}

# --- Databricks-delegated subnets (VNet injection: "public"/host + "private"/container) ---
# Both are private in practice (no_public_ip = true on the workspace); the
# public/private naming is Azure Databricks' own naming convention for the
# two subnets VNet injection requires.

resource "azurerm_subnet" "databricks_public" {
  name                 = "snet-databricks-public"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_cidrs["databricks_public"]]

  delegation {
    name = "databricks-delegation"
    service_delegation {
      name = "Microsoft.Databricks/workspaces"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
      ]
    }
  }
}

resource "azurerm_subnet" "databricks_private" {
  name                 = "snet-databricks-private"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_cidrs["databricks_private"]]

  delegation {
    name = "databricks-delegation"
    service_delegation {
      name = "Microsoft.Databricks/workspaces"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
      ]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_cidrs["private_endpoints"]]

  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_subnet" "firewall" {
  count = var.enable_firewall ? 1 : 0

  # Azure requires this exact subnet name for Azure Firewall.
  name                 = "AzureFirewallSubnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_cidrs["firewall"]]
}

# --- NSGs: required rules for Azure Databricks VNet injection with Secure ---
# --- Cluster Connectivity (no public IP). See docs/architecture/diagrams/  ---
# --- network-diagram.md for the traffic this maps to.                      ---

locals {
  databricks_nsg_rules = {
    "AllowVnetInBound" = {
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "*"
      source_port_range          = "*"
      destination_port_range     = "*"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "VirtualNetwork"
      priority                   = 100
    }
    "AllowVnetOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "*"
      source_port_range          = "*"
      destination_port_range     = "*"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "VirtualNetwork"
      priority                   = 100
    }
    "AllowDatabricksControlPlaneOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "443"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "AzureDatabricks"
      priority                   = 110
    }
    "AllowStorageOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "443"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "Storage"
      priority                   = 120
    }
    "AllowEntraIdOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "443"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "AzureActiveDirectory"
      priority                   = 130
    }
    "AllowEventHubOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "9093"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "EventHub"
      priority                   = 140
    }
    "AllowSqlMetastoreOutBound" = {
      direction                  = "Outbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "3306"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "Sql"
      priority                   = 150
    }
  }
}

resource "azurerm_network_security_group" "databricks_public" {
  name                = "nsg-smartmeter-${var.environment}-databricks-public"
  resource_group_name = var.resource_group_name
  location            = var.region

  dynamic "security_rule" {
    for_each = local.databricks_nsg_rules
    content {
      name                       = security_rule.key
      priority                   = security_rule.value.priority
      direction                  = security_rule.value.direction
      access                     = security_rule.value.access
      protocol                   = security_rule.value.protocol
      source_port_range          = security_rule.value.source_port_range
      destination_port_range     = security_rule.value.destination_port_range
      source_address_prefix      = security_rule.value.source_address_prefix
      destination_address_prefix = security_rule.value.destination_address_prefix
    }
  }

  tags = var.tags
}

resource "azurerm_network_security_group" "databricks_private" {
  name                = "nsg-smartmeter-${var.environment}-databricks-private"
  resource_group_name = var.resource_group_name
  location            = var.region

  dynamic "security_rule" {
    for_each = local.databricks_nsg_rules
    content {
      name                       = security_rule.key
      priority                   = security_rule.value.priority
      direction                  = security_rule.value.direction
      access                     = security_rule.value.access
      protocol                   = security_rule.value.protocol
      source_port_range          = security_rule.value.source_port_range
      destination_port_range     = security_rule.value.destination_port_range
      source_address_prefix      = security_rule.value.source_address_prefix
      destination_address_prefix = security_rule.value.destination_address_prefix
    }
  }

  tags = var.tags
}

resource "azurerm_subnet_network_security_group_association" "databricks_public" {
  subnet_id                 = azurerm_subnet.databricks_public.id
  network_security_group_id = azurerm_network_security_group.databricks_public.id
}

resource "azurerm_subnet_network_security_group_association" "databricks_private" {
  subnet_id                 = azurerm_subnet.databricks_private.id
  network_security_group_id = azurerm_network_security_group.databricks_private.id
}

# --- Azure Firewall: sole egress path for the Databricks subnets when enabled ---

resource "azurerm_public_ip" "firewall" {
  count = var.enable_firewall ? 1 : 0

  name                = "pip-smartmeter-${var.environment}-firewall"
  resource_group_name = var.resource_group_name
  location            = var.region
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_firewall_policy" "this" {
  count = var.enable_firewall ? 1 : 0

  name                = "afwp-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_firewall" "this" {
  count = var.enable_firewall ? 1 : 0

  name                = "afw-smartmeter-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.region
  sku_name            = "AZFW_VNet"
  sku_tier            = "Standard"
  firewall_policy_id  = azurerm_firewall_policy.this[0].id

  ip_configuration {
    name                 = "fw-ipconfig"
    subnet_id            = azurerm_subnet.firewall[0].id
    public_ip_address_id = azurerm_public_ip.firewall[0].id
  }

  tags = var.tags
}

resource "azurerm_firewall_policy_rule_collection_group" "this" {
  count = var.enable_firewall ? 1 : 0

  name               = "rcg-smartmeter-${var.environment}-egress"
  firewall_policy_id = azurerm_firewall_policy.this[0].id
  priority           = 200

  application_rule_collection {
    name     = "allow-package-repos"
    priority = 210
    action   = "Allow"

    rule {
      name = "allowed-fqdns"
      protocols {
        type = "Https"
        port = 443
      }
      source_addresses  = var.vnet_address_space
      destination_fqdns = var.firewall_allowed_fqdns
    }
  }

  network_rule_collection {
    name     = "allow-azure-platform"
    priority = 220
    action   = "Allow"

    rule {
      name                  = "databricks-control-plane"
      protocols             = ["TCP"]
      source_addresses      = var.vnet_address_space
      destination_addresses = ["AzureDatabricks"]
      destination_ports     = ["443"]
    }

    rule {
      name                  = "azure-storage"
      protocols             = ["TCP"]
      source_addresses      = var.vnet_address_space
      destination_addresses = ["Storage"]
      destination_ports     = ["443"]
    }

    rule {
      name                  = "azure-ad"
      protocols             = ["TCP"]
      source_addresses      = var.vnet_address_space
      destination_addresses = ["AzureActiveDirectory"]
      destination_ports     = ["443"]
    }

    rule {
      name                  = "event-hub"
      protocols             = ["TCP"]
      source_addresses      = var.vnet_address_space
      destination_addresses = ["EventHub"]
      destination_ports     = ["9093", "443"]
    }
  }
}

resource "azurerm_route_table" "egress_via_firewall" {
  count = var.enable_firewall ? 1 : 0

  name                          = "rt-smartmeter-${var.environment}-egress"
  resource_group_name           = var.resource_group_name
  location                      = var.region
  bgp_route_propagation_enabled = false
  tags                          = var.tags

  route {
    name                   = "default-via-firewall"
    address_prefix         = "0.0.0.0/0"
    next_hop_type          = "VirtualAppliance"
    next_hop_in_ip_address = azurerm_firewall.this[0].ip_configuration[0].private_ip_address
  }
}

resource "azurerm_subnet_route_table_association" "databricks_public" {
  count = var.enable_firewall ? 1 : 0

  subnet_id      = azurerm_subnet.databricks_public.id
  route_table_id = azurerm_route_table.egress_via_firewall[0].id
}

resource "azurerm_subnet_route_table_association" "databricks_private" {
  count = var.enable_firewall ? 1 : 0

  subnet_id      = azurerm_subnet.databricks_private.id
  route_table_id = azurerm_route_table.egress_via_firewall[0].id
}

# --- Private DNS zones for privatelink-enabled PaaS dependencies ---

resource "azurerm_private_dns_zone" "this" {
  for_each = toset(var.private_dns_zone_names)

  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each = azurerm_private_dns_zone.this

  name                  = "link-${replace(each.value.name, ".", "-")}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = each.value.name
  virtual_network_id    = azurerm_virtual_network.this.id
  registration_enabled  = false
}
