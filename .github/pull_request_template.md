## What changed and why

<!-- One or two sentences. Link the ADR if this implements/changes a documented decision. -->

## Checklist

- [ ] `ruff check` / `black --check` pass (or will via CI)
- [ ] `pytest tests/unit` passes (or will via CI)
- [ ] If this touches `terraform/**`: `terraform fmt -check -recursive` passes, and the CI-posted `terraform plan` comment has been reviewed
- [ ] If this adds/changes a significant, hard-to-reverse decision: an ADR is included (`docs/decisions/ADR-00NN-*.md`) and `docs/decisions/README.md`'s index is updated
- [ ] Relevant docs updated (module/guide READMEs, `README.md`'s Delivery Phases table if a phase's status changed)

## Test plan

<!-- How was this verified? Unit tests added/run, manual steps taken, etc. -->
