"""Unit tests for src/ml/vector_search/build_kpi_glossary_index.py's pure
chunking logic. `sync_vector_search_index` (requires a live Databricks
workspace + databricks-vectorsearch) is intentionally not exercised here.
"""

from __future__ import annotations

from src.ml.vector_search.build_kpi_glossary_index import (
    GLOSSARY_DIR,
    chunk_markdown_by_section,
    load_glossary_chunks,
)

SAMPLE_MARKDOWN = """# Title

Intro paragraph, not part of any section.

## First Term

Definition of the first term.

## Second Term

Definition of the second term, with **bold** text.
"""


def test_chunk_markdown_by_section_splits_on_h2_headings():
    chunks = chunk_markdown_by_section("sample.md", SAMPLE_MARKDOWN)

    assert len(chunks) == 2
    assert chunks[0].section_title == "First Term"
    assert chunks[1].section_title == "Second Term"


def test_chunk_markdown_by_section_content_includes_its_own_heading():
    chunks = chunk_markdown_by_section("sample.md", SAMPLE_MARKDOWN)

    assert chunks[0].content.startswith("## First Term")
    assert "Definition of the first term" in chunks[0].content
    # Should not bleed into the next section's content.
    assert "Second Term" not in chunks[0].content


def test_chunk_markdown_by_section_generates_stable_unique_ids():
    chunks = chunk_markdown_by_section("sample.md", SAMPLE_MARKDOWN)

    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert ids[0] == "sample.md::first-term"


def test_chunk_markdown_by_section_handles_no_headings():
    assert chunk_markdown_by_section("empty.md", "Just a paragraph, no headings.") == []


def test_load_glossary_chunks_reads_real_glossary_docs():
    chunks = load_glossary_chunks(GLOSSARY_DIR)

    assert len(chunks) > 0
    source_docs = {c.source_doc for c in chunks}
    assert "kpi_glossary.md" in source_docs
    assert "gold_table_reference.md" in source_docs
    assert "business_terms.md" in source_docs
    # Every chunk must carry real content, not an empty/whitespace-only match.
    assert all(len(c.content.strip()) > 20 for c in chunks)
