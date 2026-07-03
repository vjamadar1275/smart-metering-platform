# Terraform — Infrastructure as Code

## Scope as of Phase 2

**Implemented** (real `azurerm_*` / `databricks_*` resources, wired into dev/staging/prod): `networking`, `key-vault`, `managed-identity`, `storage`, `databricks-workspace`, `unity-catalog` — this is Phase 2, "Infrastructure: Databricks Workspace, Unity Catalog, Networking," per the [delivery phase plan](../README.md#delivery-phases).

**Interface-only** (variables/outputs defined, resources added in their own phase): `event-hub` (Phase 3), `sql-warehouse` (Phase 6), `monitoring` (Phase 8).

`terraform init` / `fmt` / `validate` pass for all three environments today. `terraform plan` / `apply` require real Azure credentials and a bootstrapped state backend (see below) — not available in this repo's CI-less local scaffolding, so they haven't been run against live Azure yet; validate this yourself before your first real apply.

## Layout

```
terraform/
├── environments/
│   ├── dev/          Root module for the dev environment
│   ├── staging/       Root module for the staging environment
│   └── prod/          Root module for the prod environment (+ secondary DR region)
└── modules/
    ├── networking/            VNet, subnets, NSGs, Private DNS zones, Azure Firewall
    ├── storage/                ADLS Gen2 (hierarchical namespace), lifecycle policies
    ├── key-vault/               Key Vault (Premium, HSM), access policies
    ├── managed-identity/        User-assigned Managed Identities per workload
    ├── event-hub/                Event Hubs namespace (Dedicated), hub, consumer groups, Geo-DR
    ├── databricks-workspace/     VNet-injected Databricks workspace, SCC
    ├── unity-catalog/             Metastore, catalogs, schemas, external locations, storage credentials
    ├── sql-warehouse/             BI / ad hoc / executive SQL Warehouses
    └── monitoring/                Log Analytics, diagnostic settings, alert rules
```

Each environment root module calls the shared modules with environment-specific variables — no resource logic is duplicated between dev/staging/prod, only configuration values (`*.tfvars`).

## State Backend

Terraform state is stored remotely in an **Azure Storage Account with GRS + versioning + soft delete**, separate from the platform's own data storage accounts (see [ADR rationale in the DR diagram](../docs/architecture/diagrams/disaster-recovery-diagram.md#backup-strategy-independent-of-regional-dr)). One blob container, one state file (key) per environment:

| Environment | Storage Account | Container | State key |
|---|---|---|---|
| dev | `stsmtrtfstateeus2` | `tfstate` | `dev/smartmetering.tfstate` |
| staging | `stsmtrtfstateeus2` | `tfstate` | `staging/smartmetering.tfstate` |
| prod | `stsmtrtfstateeus2` | `tfstate` | `prod/smartmetering.tfstate` |

**Bootstrap note**: the state storage account itself cannot be created by the Terraform it will store state for (chicken-and-egg). It is provisioned once, out-of-band, via `tools/bootstrap/` (added when Phase 2 infrastructure work begins) or manually by a platform admin, with the exact `az` CLI commands documented in the (Phase 2) Deployment Guide.

## Workflow

```bash
cd terraform/environments/dev
terraform init                          # downloads providers, configures backend
terraform fmt -check -recursive         # style check
terraform validate                      # syntax/internal-consistency check
terraform plan -var-file=terraform.tfvars   # (Phase 2+) shows planned resource changes
```

CI/CD (`.github/workflows/`, added in Phase 8) runs `fmt -check`, `validate`, and `plan` on every pull request touching `terraform/**`, with `apply` gated behind manual approval per environment.

## Conventions

- **Naming**: `<resource-abbrev>-smartmeter-<component>-<env>[-<region-abbrev>]`, e.g. `rg-smartmeter-data-prod`, `evhns-smartmeter-telemetry-prod`.
- **Tagging**: every resource is tagged `environment`, `owner`, `cost-center`, `data-classification` — enforced via a common `locals.tags` map in each environment root module, not repeated per resource.
- **No hardcoded secrets**: all secrets/connection strings flow through Key Vault references or Terraform-managed Databricks secret scopes — never plain `tfvars` values. `*.tfvars` (real, non-example files) are gitignored.
- **Module versioning**: modules are consumed by relative path within this repo (monorepo IaC), not a separate module registry — appropriate at this repo's scale; revisit only if modules need to be shared outside this platform.
