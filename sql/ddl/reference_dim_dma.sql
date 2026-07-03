-- Reference DDL for reference.dim_dma — documentation only.
--
-- The actual table is created and populated by src/jobs/seed_reference_data.py
-- (see bundles/seed_reference_data_job.yml for deployment). Do not run this
-- file against a live catalog; it exists so the table's shape is reviewable
-- in plain SQL without reading Python, per CONTRIBUTING.md's DDL
-- documentation convention.
--
-- District Meter Areas change composition rarely (network re-zoning), so
-- unlike dim_meter/dim_customer this is kept Type 1 (overwrite in place) —
-- SCD2 history was judged not worth the complexity for a table this small
-- and this stable; revisit if DMA boundary changes need historical Gold
-- reporting fidelity.

CREATE TABLE IF NOT EXISTS reference.dim_dma (
    dma_id                 STRING      COMMENT 'District Meter Area identifier. Matches silver.meter_readings.dma_id.',
    dma_name                STRING      COMMENT 'Human-readable DMA name.',
    zone                     STRING      COMMENT 'Broader geographic zone this DMA belongs to (North/South/East/West/Central).',
    supply_source            STRING      COMMENT 'SURFACE_WATER | GROUNDWATER | BLENDED.',
    population_served        INT         COMMENT 'Approximate population served within this DMA.',
    target_nrw_pct           DOUBLE      COMMENT 'Target non-revenue-water percentage from the utility''s water-balance audit; gold.dma_analytics compares actual NRW against this.'
)
USING DELTA
COMMENT 'District Meter Area dimension. Reference data joined into Silver enrichment and Gold''s dma_analytics non-revenue-water calculation. See docs/architecture/ARCHITECTURE.md#4-silver--gold.'
TBLPROPERTIES (
    'quality' = 'reference'
);
