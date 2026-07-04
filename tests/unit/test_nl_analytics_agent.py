"""Unit tests for src/ml/agent/nl_analytics_agent.py.

`ask()`'s three collaborators (retrieval, generation, execution) are
injected as plain functions, so the orchestration and — most importantly —
the SQL safety validation can be tested with fakes, no live Vector Search
index / Model Serving endpoint / SQL Warehouse required.
"""

from __future__ import annotations

import pytest

from src.ml.agent.nl_analytics_agent import (
    ask,
    build_prompt,
    extract_sql_from_model_response,
    validate_readonly_query,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT dma_id, non_revenue_water_pct FROM gold.dma_analytics",
        "select * from gold.daily_usage where reading_date = current_date()",
        "WITH recent AS (SELECT * FROM gold.daily_usage) SELECT * FROM recent",
        "SELECT m.dma_id FROM reference.dim_dma m",
    ],
)
def test_validate_readonly_query_accepts_safe_gold_reference_selects(sql):
    is_safe, reason = validate_readonly_query(sql)
    assert is_safe is True
    assert reason is None


@pytest.mark.parametrize(
    "sql,expected_fragment",
    [
        ("DROP TABLE gold.daily_usage", "must be a SELECT"),
        ("DELETE FROM gold.daily_usage", "must be a SELECT"),
        (
            "SELECT * FROM gold.daily_usage; DROP TABLE gold.daily_usage",
            "Exactly one SQL statement",
        ),
        ("SELECT * FROM quarantine.silver_meter_readings", "disallowed schema"),
        ("SELECT * FROM silver.meter_readings", "disallowed schema"),
        ("SELECT * FROM ml.leak_detection_model", "disallowed schema"),
        (
            "SELECT * FROM gold.daily_usage WHERE meter_id IN "
            "(SELECT meter_id FROM bronze.meter_telemetry)",
            "disallowed schema",
        ),
        ("not even sql at all garbage {{{", "could not be parsed"),
        ("SELECT * FROM daily_usage", "disallowed schema"),  # unqualified table, no schema at all
    ],
)
def test_validate_readonly_query_rejects_unsafe_queries(sql, expected_fragment):
    is_safe, reason = validate_readonly_query(sql)
    assert is_safe is False
    assert expected_fragment in reason


def test_build_prompt_includes_context_and_allowed_schemas():
    system_prompt, user_prompt = build_prompt(
        "What is our leak rate?", ["## Non-revenue water (NRW)\nDefinition..."]
    )

    assert "gold, reference" in system_prompt
    assert "Non-revenue water (NRW)" in system_prompt
    assert user_prompt == "What is our leak rate?"


def test_build_prompt_handles_no_context():
    system_prompt, _ = build_prompt("some question", [])
    assert "no relevant glossary context found" in system_prompt


def test_extract_sql_from_model_response_pulls_fenced_block():
    response = (
        "Here is your query:\n```sql\nSELECT 1 AS x\n```\nLet me know if you need anything else."
    )
    assert extract_sql_from_model_response(response) == "SELECT 1 AS x"


def test_extract_sql_from_model_response_raises_without_fenced_block():
    with pytest.raises(ValueError):
        extract_sql_from_model_response("Sure, the answer is SELECT 1.")


def test_ask_executes_when_generated_sql_is_safe():
    def fake_retrieve(question, top_k):
        return ["## Some KPI\nDefinition."]

    def fake_generate(system_prompt, user_prompt):
        return "```sql\nSELECT dma_id FROM gold.dma_analytics\n```"

    def fake_execute(sql):
        return [{"dma_id": "DMA-001"}]

    response = ask(
        "Which DMA has the most leaks?",
        retrieve_context_fn=fake_retrieve,
        generate_sql_fn=fake_generate,
        execute_query_fn=fake_execute,
    )

    assert response.is_safe is True
    assert response.result_rows == [{"dma_id": "DMA-001"}]
    assert response.generated_sql == "SELECT dma_id FROM gold.dma_analytics"


def test_ask_does_not_execute_unsafe_generated_sql():
    calls = []

    def fake_retrieve(question, top_k):
        return []

    def fake_generate(system_prompt, user_prompt):
        return "```sql\nDROP TABLE gold.daily_usage\n```"

    def fake_execute(sql):
        calls.append(sql)
        return [{"should": "not run"}]

    response = ask(
        "Delete everything",
        retrieve_context_fn=fake_retrieve,
        generate_sql_fn=fake_generate,
        execute_query_fn=fake_execute,
    )

    assert response.is_safe is False
    assert response.rejection_reason is not None
    assert response.result_rows == []
    assert calls == []  # execute_query_fn must never be called for an unsafe query
