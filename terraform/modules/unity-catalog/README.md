# Module: unity-catalog

Provisions the Unity Catalog metastore, storage credential + external location (backed by the `storage` module's ADLS account), and the catalog/schema layout defined in [ADR-0006](../../../docs/decisions/ADR-0006-unity-catalog-strategy.md) (catalog-per-environment, schema-per-domain: `bronze`, `silver`, `gold`, `ml`, `quarantine`, `reference`).

**Status**: implemented (Phase 2).
