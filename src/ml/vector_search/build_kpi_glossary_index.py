"""Builds/refreshes the KPI/glossary Mosaic AI Vector Search index (Phase 7)
that `src/ml/agent/nl_analytics_agent.py` retrieves from for RAG grounding,
per ADR-0008.

Source content: `docs/glossary/*.md` (this platform's own KPI definitions,
Gold table reference, and business terminology) — chunked by markdown `##`
section into `<catalog>.ml.kpi_glossary_chunks`, then synced into a Vector
Search index over that Delta table (managed embeddings via a Databricks
Foundation Model API endpoint, per ADR-0008's "no duplicated data
movement/sync problem" rationale for Mosaic AI Vector Search).

A plain batch Databricks Job task (src/ml/vector_search/, not a Lakeflow
pipeline — same "one-off/low-frequency, not a continuous transformation"
reasoning as src/jobs/seed_reference_data.py), triggered whenever the
glossary docs change or on a low-frequency schedule (see
bundles/vector_search.yml) — glossary content changes far less often than
Gold data does.

Usage (Databricks Job task):
    python -m src.ml.vector_search.build_kpi_glossary_index --catalog smartmeter_dev
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from pyspark.sql import SparkSession

GLOSSARY_DIR = Path(__file__).resolve().parents[3] / "docs" / "glossary"
VECTOR_SEARCH_ENDPOINT_NAME = "smartmeter-kpi-glossary-endpoint"
GLOSSARY_TABLE_NAME = "ml.kpi_glossary_chunks"
EMBEDDING_MODEL_ENDPOINT = "databricks-gte-large-en"

_SECTION_HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class GlossaryChunk:
    chunk_id: str
    source_doc: str
    section_title: str
    content: str


def chunk_markdown_by_section(source_doc: str, markdown_text: str) -> list[GlossaryChunk]:
    """Splits a markdown document into one chunk per `##` section (the
    glossary docs' entry-per-term/table granularity), dropping the
    top-level `#` title. Each chunk keeps its own heading as part of the
    content, so retrieval surfaces context (e.g. "## Non-revenue water
    (NRW)...") rather than a bare, unattributed paragraph.
    """
    headings = list(_SECTION_HEADING_RE.finditer(markdown_text))
    chunks = []
    for i, match in enumerate(headings):
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown_text)
        section_title = match.group(1).strip()
        content = markdown_text[start:end].strip()
        chunk_id = f"{source_doc}::{section_title}".lower().replace(" ", "-")
        chunks.append(GlossaryChunk(chunk_id, source_doc, section_title, content))
    return chunks


def load_glossary_chunks(glossary_dir: Path = GLOSSARY_DIR) -> list[GlossaryChunk]:
    chunks = []
    for md_file in sorted(glossary_dir.glob("*.md")):
        chunks.extend(chunk_markdown_by_section(md_file.name, md_file.read_text()))
    return chunks


def write_glossary_chunks_table(
    spark: SparkSession, catalog: str, chunks: list[GlossaryChunk]
) -> None:
    df = spark.createDataFrame(
        [(c.chunk_id, c.source_doc, c.section_title, c.content) for c in chunks],
        ["chunk_id", "source_doc", "section_title", "content"],
    )
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{catalog}.{GLOSSARY_TABLE_NAME}"
    )


def sync_vector_search_index(catalog: str) -> None:
    """Creates the Vector Search endpoint/index if absent, else triggers a
    sync of the existing index against `kpi_glossary_chunks`'s latest
    content. Requires a live Databricks workspace and the
    `databricks-vectorsearch` SDK — not exercised by
    tests/unit/test_vector_search.py, which covers the pure chunking logic
    above instead (`chunk_markdown_by_section`, `load_glossary_chunks`).
    """
    from databricks.vector_search.client import VectorSearchClient

    client = VectorSearchClient()
    source_table = f"{catalog}.{GLOSSARY_TABLE_NAME}"
    index_name = f"{catalog}.ml.kpi_glossary_index"

    existing_endpoints = {e["name"] for e in client.list_endpoints().get("endpoints", [])}
    if VECTOR_SEARCH_ENDPOINT_NAME not in existing_endpoints:
        client.create_endpoint(name=VECTOR_SEARCH_ENDPOINT_NAME, endpoint_type="STANDARD")

    existing_indexes = {
        idx["name"]
        for idx in client.list_indexes(VECTOR_SEARCH_ENDPOINT_NAME).get("vector_indexes", [])
    }
    if index_name not in existing_indexes:
        client.create_delta_sync_index(
            endpoint_name=VECTOR_SEARCH_ENDPOINT_NAME,
            index_name=index_name,
            source_table_name=source_table,
            pipeline_type="TRIGGERED",
            primary_key="chunk_id",
            embedding_source_column="content",
            embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
        )
    else:
        client.get_index(VECTOR_SEARCH_ENDPOINT_NAME, index_name).sync()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", required=True, help="Unity Catalog catalog, e.g. smartmeter_dev."
    )
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    chunks = load_glossary_chunks()
    write_glossary_chunks_table(spark, args.catalog, chunks)
    sync_vector_search_index(args.catalog)


if __name__ == "__main__":
    main()
