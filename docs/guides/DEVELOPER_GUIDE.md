# Developer Guide

Local setup, coding standards, testing conventions, and PR workflow — the day-to-day reference for contributing to this repository. [CONTRIBUTING.md](../../CONTRIBUTING.md) is the source of truth for standards; this guide is the "how do I actually run things" companion.

## Local setup

```bash
git clone <repo-url> && cd smart-metering-platform
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pins `pyspark`/`delta-spark` at the same major versions the Databricks Runtime provides, plus `mlflow`/`scikit-learn`/`sqlglot` for `src/ml/`, plus `databricks-sdk`/`databricks-sql-connector` (only exercised by `tests/integration/`, which skips without live credentials). A JDK (17+) is required locally for the embedded Spark JVM `tests/conftest.py`'s `spark` fixture starts — `brew install openjdk@17` / `apt install openjdk-17-jdk` / equivalent.

## Running things locally

```bash
# Unit tests — real local PySpark + Delta + MLflow + sklearn, no live workspace needed
pytest tests/unit

# Performance regression guards (~45K-row synthetic scale, always run)
pytest tests/performance

# Lint / format
ruff check src tests tools
black --check src tests tools

# Terraform — syntax/formatting only, no credentials needed
cd terraform/environments/dev
terraform fmt -check -recursive
terraform init -backend=false && terraform validate

# Generate synthetic data locally (no Event Hub needed)
python -m tools.mock_data_generator.cli --meters 1000 --hours 24 --out-dir ./mock_data
```

`tests/integration/` and `tests/load/` require a live Databricks workspace / Event Hub and skip automatically without credentials (see their own READMEs) — you cannot exercise them from a machine without real Azure/Databricks access, which is expected; this repository has never been applied to live infrastructure (see [terraform/README.md](../../terraform/README.md)).

## Repository conventions (quick reference — see CONTRIBUTING.md for the full list)

- **Branching**: `feature/<phase>-<short-description>`.
- **Python**: Black (line length 100) + ruff. Type hints required in `src/libs/`. No bare `except:`. Structured JSON logging via `src/libs/monitoring/` — no bare `print()` in pipeline code.
- **SQL**: uppercase keywords, lowercase identifiers, one clause per line beyond trivial queries, every table comment mandatory.
- **Terraform**: `fmt -recursive` before every commit; every variable has a `description`; every taggable resource is tagged with `local.standard_tags`.
- **No hardcoded environment values** — sourced from `src/config/<env>/` or bundle variables, never a string literal in pipeline code.

## Where things live (by layer)

| Layer | Pipeline code | Shared logic | DDL reference | Bundle config |
|---|---|---|---|---|
| Bronze | `src/pipelines/bronze/` | — | `sql/ddl/bronze_*.sql` | `bundles/bronze_pipeline.yml` |
| Silver | `src/pipelines/silver/` | `src/libs/quality/`, `src/libs/common/enrichment.py` | `sql/ddl/silver_*.sql`, `sql/ddl/quarantine_*.sql` | `bundles/silver_pipeline.yml`, `bundles/silver_late_arrival_reconciliation_job.yml` |
| Gold | `src/pipelines/gold/` | `src/libs/common/gold_transforms.py` | `sql/ddl/gold_*.sql` | `bundles/gold_streaming_pipeline.yml`, `bundles/gold_batch_pipeline.yml` |
| ML | `src/ml/training/`, `src/ml/agent/` | `src/ml/features/` | `sql/ddl/ml_*.sql` | `bundles/ml_training_jobs.yml`, `bundles/model_serving.yml`, `bundles/vector_search.yml` |
| Reference data | `src/jobs/seed_reference_data.py` | `tools/mock_data_generator/generator.py` | `sql/ddl/reference_*.sql` | `bundles/seed_reference_data_job.yml` |

Notice the pattern: pipeline files in `src/pipelines/<layer>/` are thin — they read a source, call a function from `src/libs/`, write a target. The actual transformation logic lives in `src/libs/`/`src/ml/features/` specifically so it's unit-testable with local PySpark without a running Lakeflow pipeline (see any `tests/unit/test_*.py` for the pattern — e.g. `test_gold_transforms.py` tests `src/libs/common/gold_transforms.py` directly).

## Adding a new Gold table or ML model

1. Write the transform as a pure `DataFrame -> DataFrame` function in `src/libs/common/` (Gold) or `src/ml/features/` (ML feature engineering) — no `dp.table`/MLflow calls inside it.
2. Unit test that function with small, hand-built fixtures (exact expected values, not just "it runs").
3. Wire it into a thin `src/pipelines/gold/*.py` (Gold) or `src/ml/training/*.py` (ML) file that just reads the input table(s) and calls your function.
4. Add reference DDL under `sql/ddl/` documenting the output shape (see any existing `gold_*.sql` for the format).
5. Wire the bundle resource (`bundles/*.yml`) if it's a new pipeline/job, or add it to an existing one's task list.
6. If this is a significant, hard-to-reverse decision (a new proxy metric, a new model framing choice, a new pipeline-cadence split) — write an ADR (`docs/decisions/ADR-00NN-*.md`, next sequential number) and update `docs/decisions/README.md`'s index.
7. Update `README.md`'s Delivery Phases table only when the *whole phase* is done, not per-artifact.

## Getting help

Start with [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) and the [ADRs](../decisions/) for *why* something is designed the way it is. This guide and [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) cover *how* to work with it day to day.
