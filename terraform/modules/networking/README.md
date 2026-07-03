# Module: networking

Provisions the VNet, subnets (public/NAT, Databricks-private, private-endpoints, firewall), NSGs, Azure Firewall, and Private DNS zones described in [docs/architecture/diagrams/network-diagram.md](../../../docs/architecture/diagrams/network-diagram.md).

**Status**: interface defined (Phase 1); resources implemented in Phase 2.

## Inputs / Outputs

See [variables.tf](variables.tf) and [outputs.tf](outputs.tf) for the full contract. Summary:

- **In**: environment, region, resource group, VNet address space, per-subnet CIDRs, tags.
- **Out**: VNet ID, a map of subnet name → subnet ID (consumed by `databricks-workspace` for VNet injection and by `storage`/`event-hub`/`key-vault` for Private Endpoint placement), NSG IDs, Private DNS zone IDs.
