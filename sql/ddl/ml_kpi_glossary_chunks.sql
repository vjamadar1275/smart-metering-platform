-- Reference DDL for ml.kpi_glossary_chunks — documentation only.
--
-- The actual table is created and overwritten by
-- src/ml/vector_search/build_kpi_glossary_index.py (see
-- bundles/vector_search.yml for deployment). Do not run this file against
-- a live catalog; it exists so the table's shape is reviewable in plain
-- SQL without reading Python, per CONTRIBUTING.md's DDL documentation
-- convention.
--
-- Source table for the `kpi_glossary_index` Mosaic AI Vector Search index
-- (Delta Sync, managed embeddings) — see ADR-0008/ADR-0012.

CREATE TABLE IF NOT EXISTS ml.kpi_glossary_chunks (
    chunk_id           STRING      COMMENT 'Primary key: "<source_doc>::<section-title>", lowercased/hyphenated. Stable across re-runs as long as the source doc''s section heading text does not change.',
    source_doc          STRING      COMMENT 'Filename under docs/glossary/ this chunk came from.',
    section_title         STRING      COMMENT 'The markdown ## heading this chunk was extracted from.',
    content                STRING      COMMENT 'Full chunk text (heading + body), the column Vector Search embeds.'
)
USING DELTA
COMMENT 'KPI/glossary documentation chunks, source table for the kpi_glossary_index Vector Search index. See docs/glossary/, src/ml/vector_search/build_kpi_glossary_index.py, ADR-0008.'
TBLPROPERTIES (
    'quality' = 'ml'
);
