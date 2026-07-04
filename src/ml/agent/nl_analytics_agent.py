"""A simple NL analytics / agentic assistant (Phase 7), per ADR-0008 and
ADR-0012.

Flow: retrieve grounding context from the KPI/glossary Vector Search index
(`src/ml/vector_search/build_kpi_glossary_index.py`) -> build a prompt ->
call a Databricks Model Serving chat-completions endpoint (a foundation
model, accessed through Databricks' governed external-model proxy per
ADR-0008, never called directly) to generate a read-only SQL query against
Gold -> validate the query is actually read-only and scoped to
gold/reference before ever executing it -> run it against `sqlw-adhoc` and
return the result alongside the grounding context that produced it.

Deliberately simple, not a multi-tool agent framework: one retrieval step,
one generation step, one validated execution step. Widening this (multi-turn
conversation, tool-calling, write-back actions) is future work, not
attempted here — see ADR-0012.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

ALLOWED_SCHEMAS = ("gold", "reference")

SYSTEM_PROMPT_TEMPLATE = (
    "You are a read-only SQL analytics assistant for a water utility's Smart Metering Platform.\n"
    "You may only write SELECT queries against these Unity Catalog schemas: {allowed_schemas}.\n"
    "Never write INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, GRANT, or any other "
    "data-modifying statement.\n"
    "Use the glossary context below to ground table/column choices and to caveat any "
    "non-revenue-water or predictive-model figures as estimates, not measured facts.\n"
    "Respond with exactly one SQL query in a ```sql code block, and nothing else.\n"
    "\n"
    "Glossary context:\n"
    "{context}\n"
)


@dataclass(frozen=True)
class AgentResponse:
    question: str
    context_chunks: list[str]
    generated_sql: str
    is_safe: bool
    rejection_reason: str | None = None
    result_rows: list[dict] = field(default_factory=list)


def build_prompt(question: str, context_chunks: list[str]) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the chat-completions call."""
    context = (
        "\n\n".join(context_chunks) if context_chunks else "(no relevant glossary context found)"
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        allowed_schemas=", ".join(ALLOWED_SCHEMAS), context=context
    )
    return system_prompt, question


def extract_sql_from_model_response(response_text: str) -> str:
    """Pulls the SQL out of a ```sql ... ``` fenced code block. Raises
    ValueError if the model didn't follow the requested format — treated
    as a hard failure (no query to run), not something to guess-parse.
    """
    match = re.search(r"```sql\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("Model response did not contain a ```sql fenced code block.")
    return match.group(1).strip()


def validate_readonly_query(sql: str) -> tuple[bool, str | None]:
    """Returns (is_safe, rejection_reason). A query is safe only if it:
    1. Parses as valid SQL — an unparseable query is rejected outright
       rather than guessed at.
    2. Is exactly one statement (rejects `SELECT ...; DROP TABLE ...`
       multi-statement injection).
    3. Is a SELECT/UNION query — real parsing (via `sqlglot`), not a
       keyword blocklist, is what rules out DROP/INSERT/UPDATE/DELETE/
       CREATE/ALTER/etc.: a regex keyword check is both bypassable
       (obfuscation, keywords inside string literals/identifiers) and
       prone to false positives (a column named e.g. `update_count`), so
       statement *type* is checked structurally instead.
    4. Only references tables in ALLOWED_SCHEMAS (gold/reference) — never
       quarantine, bronze, silver, or ml (raw/intermediate/model-internal
       data this assistant has no business surfacing to an analyst).
       CTE self-references (e.g. `WITH recent AS (...) SELECT * FROM
       recent`) are excluded from this check — `recent` is not a schema.
    """
    try:
        statements = sqlglot.parse(sql, read="databricks")
    except Exception as e:
        return False, f"Query could not be parsed as SQL: {e}"

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return False, "Exactly one SQL statement is required (no multi-statement queries)."

    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union)):
        return False, f"Query must be a SELECT, not {type(statement).__name__}."

    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    disallowed_refs = set()
    for table in statement.find_all(exp.Table):
        if not table.db and table.name.lower() in cte_names:
            continue  # a reference to a CTE defined in this same query, not a real table
        if not table.db or table.db.lower() not in ALLOWED_SCHEMAS:
            disallowed_refs.add(f"{table.db or '(no schema)'}.{table.name}")

    if disallowed_refs:
        return False, f"Query references disallowed schema(s)/table(s): {sorted(disallowed_refs)}."

    return True, None


def ask(
    question: str,
    *,
    retrieve_context_fn,
    generate_sql_fn,
    execute_query_fn,
    top_k: int = 5,
) -> AgentResponse:
    """Orchestrates the full ask: retrieve -> generate -> validate ->
    (maybe) execute.

    The three collaborators are injected rather than hardcoded to a
    specific Vector Search / Model Serving / SQL Warehouse client:
    - `retrieve_context_fn(question, top_k) -> list[str]`
    - `generate_sql_fn(system_prompt, user_prompt) -> str` (raw model text)
    - `execute_query_fn(sql) -> list[dict]`

    This keeps the orchestration logic itself unit-testable with fakes
    (see tests/unit/test_nl_analytics_agent.py) without needing a live
    Vector Search index, Model Serving endpoint, or SQL Warehouse — the
    real implementations of these three functions belong in a thin
    Databricks-specific wiring module, not in this orchestration logic.
    """
    context_chunks = retrieve_context_fn(question, top_k)
    system_prompt, user_prompt = build_prompt(question, context_chunks)
    model_response = generate_sql_fn(system_prompt, user_prompt)
    generated_sql = extract_sql_from_model_response(model_response)

    is_safe, rejection_reason = validate_readonly_query(generated_sql)
    if not is_safe:
        return AgentResponse(
            question=question,
            context_chunks=context_chunks,
            generated_sql=generated_sql,
            is_safe=False,
            rejection_reason=rejection_reason,
        )

    result_rows = execute_query_fn(generated_sql)
    return AgentResponse(
        question=question,
        context_chunks=context_chunks,
        generated_sql=generated_sql,
        is_safe=True,
        result_rows=result_rows,
    )
