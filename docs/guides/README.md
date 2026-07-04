# Guides

Operational and developer documentation, added as the phases they document are implemented — a guide describing code that doesn't exist yet would go stale immediately, so each is written alongside its subject matter rather than stubbed in advance.

| Guide | Added in | Covers |
|---|---|---|
| [Developer Guide](DEVELOPER_GUIDE.md) | ✅ Phase 8 | Local setup, coding standards, testing conventions, PR workflow |
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | ✅ Phase 3 | Terraform state bootstrap, infra apply order, Databricks Asset Bundle deployment, test-traffic generation, rollback |
| [Operations Guide](OPERATIONS_GUIDE.md) | ✅ Phase 8 | Day-2 operations: pipeline restarts, backfills, scaling, on-call |
| [Security Guide](SECURITY_GUIDE.md) | ✅ Phase 8 | Key rotation, access reviews, incident response, compliance evidence |
| [Performance Guide](PERFORMANCE_GUIDE.md) | ✅ Phase 8 | Sizing methodology (and what's not yet measured), tuning playbooks |
| [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) | ✅ Phase 8 | Common failure modes and their resolutions across the pipeline |
| [API Documentation](API_DOCUMENTATION.md) | ✅ Phase 7 | Model Serving endpoint contract, NL agent interface/safety contract |

See also [docs/runbooks/](../runbooks/) for step-by-step incident-response and DR-failover procedures, and [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) / the [ADRs](../decisions/) for how the platform is designed and why.
