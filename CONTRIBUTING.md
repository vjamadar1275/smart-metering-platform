# Contributing

## Branching & PR Workflow

- `main` is always deployable to dev via CI/CD (`.github/workflows/bundle-deploy.yml`, Phase 8) — direct pushes should be disabled via GitHub branch protection (repo Settings → Branches), a GitHub-side setting this repository's code cannot itself configure; an admin should enable it requiring `lint`/`test` status checks before merge.
- Feature branches: `feature/<phase>-<short-description>` (e.g. `feature/p3-bronze-streaming`).
- One logical change per PR. PRs touching `terraform/**` automatically get a `terraform plan` comment from CI (`.github/workflows/terraform-plan.yml`, Phase 8) once that environment's credentials are configured as repo secrets.
- Environment promotion is `dev → staging → prod`, gated by manual approval at each boundary — enforced via GitHub Environment required reviewers on `bundle-deploy.yml`'s `staging`/`prod` jobs (Phase 8) — never a direct-to-prod merge.

## Coding Standards

### Python / PySpark

- **Formatting**: [Black](https://github.com/psf/black), line length 100. **Linting**: `ruff`. Both run in pre-commit and CI.
- **Type hints** on all function signatures in `src/libs/` (shared library code); optional but encouraged in pipeline/notebook code.
- **No bare `except:`** — catch specific exceptions; let unexpected exceptions propagate rather than silently swallowing them (this platform has zero-data-loss as a requirement — a silently swallowed exception in a streaming job is a data-loss bug).
- **Structured logging** via `src/libs/monitoring/` (added Phase 4) — no bare `print()` in pipeline code; log records must be queryable (JSON, with `pipeline`, `layer`, `run_id` fields) since this is how Lakehouse Monitoring and on-call diagnosis will consume them.
- **No hardcoded environment values** (workspace URLs, catalog names, storage paths) — sourced from `src/config/<env>/` at runtime, never string-literal in pipeline code, so the same code path runs unmodified in dev/staging/prod.

### SQL

- Uppercase SQL keywords, lowercase identifiers, one clause per line for anything beyond a trivial query — matches the style already used in `sql/ddl/` and Lakeflow pipeline SQL.
- Every table DDL includes a comment documenting the table's business purpose and its owning layer (Bronze/Silver/Gold) — this comment surfaces directly in Unity Catalog's UI and the data catalog, so it's not optional documentation, it's the primary documentation most business users will actually see.

### Terraform

- `terraform fmt -recursive` before every commit (enforced by pre-commit hook and CI `fmt -check`).
- Every variable has a `description`; every resource that can be tagged is tagged with the environment's `local.standard_tags`.
- No resource is created outside a module except the environment root module's resource groups and module wiring — see [terraform/README.md](terraform/README.md).

## Testing Expectations

- `src/libs/` and `src/pipelines/` require unit tests (`tests/unit/`) for any non-trivial transformation logic — added starting Phase 3.
- Integration tests (`tests/integration/`) exercise a pipeline end-to-end against a scaled-down dev dataset — added starting Phase 4.
- Performance tests (`tests/performance/`, added Phase 8) are regression guards at synthetic scale, always run (no live credentials needed) — required for a new Gold/ML transform function if it involves a window function or join whose cost could scale non-linearly.
- Load tests (`tests/load/`, added Phase 8) exercise a real Event Hub/SQL Warehouse at target throughput — skip-gated like integration tests without live credentials.
- CI (`.github/workflows/lint.yml`, `test.yml`) enforces lint + `tests/unit` + `tests/performance` on every PR; `tests/integration`/`tests/load` run too but self-skip without live credentials until an admin configures them.

## Commit Messages

Conventional, imperative mood, explain *why* not just *what*: `fix: dedupe watermark was dropping valid late-arrivals from DST-transition timestamps`, not `fix: update silver.py`.
