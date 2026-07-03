# Deployment Guide

Covers bootstrapping the Terraform state backend, applying infrastructure, and deploying the Databricks Asset Bundle. Nothing in this repository has been applied to real Azure/Databricks yet — this guide is what a platform admin runs the first time.

## 1. Bootstrap the Terraform state backend

The storage account Terraform state lives in can't be created by the Terraform it backs (chicken-and-egg) — provision it once, out-of-band:

```bash
az group create --name rg-smartmeter-tfstate --location eastus2

az storage account create \
  --name stsmtrtfstateeus2 \
  --resource-group rg-smartmeter-tfstate \
  --sku Standard_GRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

az storage account blob-service-properties update \
  --account-name stsmtrtfstateeus2 \
  --enable-versioning true \
  --enable-delete-retention true --delete-retention-days 30

az storage container create \
  --account-name stsmtrtfstateeus2 \
  --name tfstate \
  --auth-mode login
```

This matches the backend configuration in each environment's `backend.tf` (see [terraform/README.md § State Backend](../../terraform/README.md#state-backend)).

## 2. Apply infrastructure (per environment)

```bash
cd terraform/environments/dev   # or staging, prod
cp terraform.tfvars.example terraform.tfvars   # fill in real values — gitignored, never commit
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Apply order matters across environments: **dev first** (it owns the shared dev/staging Unity Catalog metastore — see [ADR-0006](../decisions/ADR-0006-unity-catalog-strategy.md)), then **staging** (reads dev's `metastore_id` output via `terraform_remote_state`), then **prod** independently (it owns its own dedicated metastore).

After `apply`, capture the outputs the Asset Bundle needs:

```bash
terraform output -raw databricks_workspace_url
terraform output vnet_id
# Event Hub namespace/name (module outputs, not surfaced at root yet — add
# root outputs if you need them scripted; today read via `terraform state show`
# or the Azure portal until Phase 6+ adds them to environment outputs.)
```

## 3. Deploy the Databricks Asset Bundle

Fill in the `REPLACE-WITH-*` placeholders in [databricks.yml](../../databricks.yml) with the real values from step 2 (workspace URL, Event Hub namespace, CI/CD service principal), then:

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run bronze_meter_telemetry -t dev
```

Promotion to staging/prod follows the same commands with `-t staging` / `-t prod`, gated by manual approval once CI/CD (Phase 8) wires this into GitHub Actions.

## 4. Generate test traffic (dev only)

```bash
export EVENTHUB_CONNECTION_STRING="$(az keyvault secret show \
    --vault-name <dev-key-vault-name> --name evhns-dev-connection-string \
    --query value -o tsv)"

python -m tools.event_hub_simulator.simulator \
    --eventhub-name evh-meter-telemetry \
    --generate --meters 500 --hours 2 --leak-rate 0.02
```

See [tools/event_hub_simulator/README.md](../../tools/event_hub_simulator/README.md) for details.

## Rollback

- **Terraform**: `terraform plan -destroy` before ever running `-destroy` for real; prefer reverting the offending commit and re-`apply`-ing over manual destroys.
- **Asset Bundle**: `databricks bundle deploy -t <env>` of a prior git commit redeploys that commit's pipeline definition; Lakeflow pipelines are versioned by the bundle deploy, not by a separate rollback mechanism.

Full CI/CD automation (linting, testing, packaging, environment promotion, approval gates) is Phase 8 — until then, every step above is run manually by a platform admin.
