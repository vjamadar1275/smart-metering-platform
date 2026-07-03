-- reference.dim_dma — District Meter Area master data.
--
-- Unlike bronze/silver DDL (which document tables that Lakeflow pipelines
-- create declaratively), this table has no upstream feed: DMAs are a small,
-- rarely-changing operational construct maintained by the utility's network
-- planning team. This script is the actual source of truth and is intended
-- to be run once per environment (after Unity Catalog's `reference` schema
-- exists — see terraform/modules/unity-catalog) and re-run to apply edits.
--
-- SCD Type 2 (effective_start_date/effective_end_date/is_current) per
-- docs/architecture/ARCHITECTURE.md#3-bronze--silver ("join against
-- slowly-changing meter/customer/DMA dimension tables ... SCD Type 2") —
-- a DMA's target_nrw_pct or supply_zone is occasionally re-baselined, and
-- Silver enrichment must attribute historical readings to the DMA
-- definition that was in effect at reading time, not today's.
--
-- Seed data below is representative, synthetic sample data for a
-- mid-size water utility — not real network topology.

CREATE TABLE IF NOT EXISTS reference.dim_dma (
    dma_sk               BIGINT      COMMENT 'Surrogate key, stable across SCD2 revisions of the same dma_id.',
    dma_id               STRING      COMMENT 'Natural key: District Meter Area identifier, matches telemetry.dma_id.',
    dma_name             STRING      COMMENT 'Human-readable DMA name.',
    region               STRING      COMMENT 'Operating region/division the DMA belongs to.',
    supply_zone          STRING      COMMENT 'Pressure/supply zone feeding this DMA.',
    connected_meter_count INT        COMMENT 'Approximate count of active meters in this DMA, for capacity/NRW context.',
    target_nrw_pct       DOUBLE      COMMENT 'Non-revenue water target, percent of supply volume (gold.dma_analytics compares actual vs. this target).',
    utc_offset_minutes   INT         COMMENT 'Local standard-time offset from UTC, minutes (e.g. -300 = UTC-5). Silver stores this alongside each UTC-normalized reading so reports can render meter-local time without a lookup, per docs/architecture/ARCHITECTURE.md#3-bronze--silver ("timezone normalization to UTC with a stored local-offset for reporting"). This utility operates in a single timezone today; per-DMA storage keeps multi-timezone expansion a data change, not a schema change.',
    effective_start_date DATE        COMMENT 'SCD2: date this DMA definition took effect.',
    effective_end_date   DATE        COMMENT 'SCD2: date this DMA definition was superseded; NULL if current.',
    is_current           BOOLEAN     COMMENT 'SCD2: true for the currently-active revision of this dma_id.'
)
USING DELTA
COMMENT 'Reference (dimension) table: District Meter Area master data, SCD Type 2. Seeded with representative data; maintained by network planning, not by a pipeline.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'reference'
);

INSERT OVERWRITE reference.dim_dma
VALUES
    (1, 'DMA-001', 'Riverside North',      'Northern Division', 'Zone A-1', 42000, 12.5, -300, DATE'2020-01-01', NULL, true),
    (2, 'DMA-002', 'Riverside South',      'Northern Division', 'Zone A-2', 38500, 14.0, -300, DATE'2020-01-01', NULL, true),
    (3, 'DMA-003', 'Harborview',           'Coastal Division',  'Zone B-1', 51200, 9.8,  -300, DATE'2020-01-01', NULL, true),
    (4, 'DMA-004', 'Millbrook Heights',    'Central Division',  'Zone C-1', 27600, 16.2, -300, DATE'2020-01-01', NULL, true),
    (5, 'DMA-005', 'Old Town',             'Central Division',  'Zone C-2', 33400, 21.4, -300, DATE'2020-01-01', NULL, true),
    (6, 'DMA-006', 'Eastgate Industrial',  'Eastern Division',  'Zone D-1', 12800, 7.1,  -300, DATE'2020-01-01', NULL, true),
    (7, 'DMA-007', 'Fairview Suburbs',     'Eastern Division',  'Zone D-2', 46900, 11.6, -300, DATE'2020-01-01', NULL, true),
    (8, 'DMA-008', 'Lakeside Estates',     'Northern Division', 'Zone A-3', 29300, 10.3, -300, DATE'2020-01-01', NULL, true);
