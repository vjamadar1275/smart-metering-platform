# API Documentation

Model Serving endpoint contract and the NL analytics agent's interface (Phase 7).

## `leak_detection_model` Model Serving endpoint

`bundles/model_serving.yml` deploys `<catalog>.ml.leak_detection_model` behind a Databricks Model Serving endpoint named `smartmeter-<env>-leak-detection`.

**Input schema** (matches `src/ml/training/train_leak_detection.py`'s `FEATURE_COLUMNS`, produced by `src/ml/features/leak_detection_features.py:build_leak_detection_features`):

| Field | Type | Description |
|---|---|---|
| `avg_night_flow_lpm` | double | A meter's average flow rate during 02:00-04:00 UTC for the day being scored. |
| `night_flow_ratio` | double | `avg_night_flow_lpm` ÷ that meter's trailing 14-day average night flow. |

**Output**: IsolationForest's `predict()` output — `1` (normal) or `-1` (anomalous/flagged). This is **not a probability or confidence score** — it's a hard classification from an unsupervised model with no real confirmed-leak ground truth to calibrate against (ADR-0012). Treat a `-1` as "worth a human looking at this meter," not as a leak confirmation.

**Request example** (REST):
```bash
curl -X POST \
  https://<workspace-url>/serving-endpoints/smartmeter-dev-leak-detection/invocations \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dataframe_records": [{"avg_night_flow_lpm": 45.2, "night_flow_ratio": 6.1}]}'
```

**Scaling**: `scale_to_zero_enabled: true` (see `bundles/model_serving.yml`'s own comment) — this endpoint is currently scored in batch against hourly-refreshed Gold features, not wired into a real-time streaming inference path, so cold-start latency after idle is an accepted trade for zero idle cost. Switching to a real-time streaming-path integration (scoring each reading as it lands in Silver) would need `scale_to_zero_enabled: false` with a provisioned minimum throughput — not implemented here.

## NL analytics agent (`src/ml/agent/nl_analytics_agent.py`)

Not deployed as its own Model Serving endpoint in this repository — it's a Python orchestration module meant to run wherever a caller has access to a Vector Search index, a Model Serving chat-completions endpoint, and a SQL Warehouse connection (e.g. a Databricks notebook, a small internal service, or wrapped in its own Model Serving custom-model deployment as a follow-up).

**Function**: `ask(question: str, *, retrieve_context_fn, generate_sql_fn, execute_query_fn, top_k: int = 5) -> AgentResponse`

| Parameter | Contract |
|---|---|
| `retrieve_context_fn(question, top_k)` | Returns `list[str]` of KPI/glossary chunk text — the real implementation queries the `kpi_glossary_index` Vector Search index (`src/ml/vector_search/build_kpi_glossary_index.py`). |
| `generate_sql_fn(system_prompt, user_prompt)` | Returns the raw chat-completion response text — the real implementation calls a Databricks Model Serving chat-completions endpoint (a foundation model, reached through Databricks' governed external-model proxy, per ADR-0008 — never called directly). |
| `execute_query_fn(sql)` | Returns `list[dict]` of result rows — the real implementation runs the validated SQL against `sqlw-adhoc` (`databricks-sql-connector`, same pattern as `tests/integration/test_silver_pipeline_integration.py`'s `sql_connection` fixture). |

**Response** (`AgentResponse`): `question`, `context_chunks`, `generated_sql`, `is_safe`, `rejection_reason` (if `is_safe` is `False`), `result_rows`.

**Safety contract**: `execute_query_fn` is **never called** unless `validate_readonly_query(generated_sql)` returns `is_safe=True` — real SQL parsing (`sqlglot`) confirms the statement is a `SELECT`/`UNION` referencing only `gold`/`reference` schema tables (ADR-0012). A caller integrating this module should treat `is_safe=False` responses as the expected, correct behavior for an unsafe or malformed model response, not an error to retry blindly.

The three injected functions (`retrieve_context_fn`/`generate_sql_fn`/`execute_query_fn`) are dependency-injected specifically so this orchestration/safety logic is unit-testable without live Vector Search/Model Serving/SQL Warehouse access — see `tests/unit/test_nl_analytics_agent.py` for the fake implementations used in tests, and write real Databricks-client-backed versions of these three functions in your integration code, not inside `nl_analytics_agent.py` itself.
