# KPI Glossary

Definitions for every metric exposed in `gold.*` — the source content Phase 7's Vector Search index (`src/ml/vector_search/build_kpi_glossary_index.py`) embeds so the NL analytics agent (`src/ml/agent/nl_analytics_agent.py`) can ground a user's question in the platform's actual metric definitions before generating SQL against Gold. Each entry names the owning table so retrieval can also suggest which table answers a question.

## Consumption metrics

**consumption_liters** (`gold.hourly_consumption`, `gold.daily_usage`) — Volumetric water usage for a meter over a time window, computed as `max(reading_value_liters) - min(reading_value_liters)` within that window (the cumulative totalizer's change, not a sum of individual deltas — robust to a missing interior reading). Always in liters regardless of the meter's original reporting unit (Silver standardizes this — see ADR-0002/ARCHITECTURE.md's Bronze → Silver section).

**trailing_7d_avg_liters** (`gold.daily_usage`) — A meter's average daily consumption over the 7 days *before* the current row (excludes the current day itself). NULL for a meter's first 7 days of history — there is no trailing baseline yet.

**usage_anomaly_flag** (`gold.daily_usage`) — True when `consumption_liters` exceeds 3x `trailing_7d_avg_liters`. A coarse, rule-based signal that only catches usage *spikes* — see `anomaly_detection_model` below for a broader multivariate model that also catches usage *drops*.

## Non-revenue water (NRW) / leak indicators — proxy caveat

**estimated_supply_liters**, **non_revenue_water_liters**, **non_revenue_water_pct**, **systemwide_nrw_pct** (`gold.dma_analytics`, `gold.executive_dashboard`) — **These are a documented proxy, not measured bulk-supply telemetry.** This platform ingests customer smart-meter readings only; there is no bulk/production meter (SCADA) data source integrated. `estimated_supply_liters` is derived as `metered_consumption_liters / (1 - target_nrw_pct/100)`, where `target_nrw_pct` comes from `reference.dim_dma`'s water-balance-audit target, not a real-time measurement. See ADR-0011 for the full rationale and the open item to replace this once a real bulk-supply integration exists. **When answering a question about NRW, always mention this is an estimate, not an audited figure.**

**avg_night_flow_lpm**, **trailing_14d_avg_night_flow_lpm**, **night_flow_anomaly_flag** (`gold.dma_analytics`) — Unlike the NRW columns above, these ARE computed from real metered data: average flow rate across a DMA's meters during 02:00–04:00 UTC (the low-demand window where sustained non-zero flow is a classic leak signature), compared against a trailing 14-day baseline. `night_flow_anomaly_flag` is true when the current night flow exceeds 2x the trailing baseline. This is the trustworthy leak indicator in `gold.dma_analytics`, independent of the NRW proxy.

## Predictive models (Phase 7, `<catalog>.ml.*`)

**leak_detection_model** — Unsupervised (IsolationForest) model scoring *per-meter* night-flow anomalies, finer-grained than `night_flow_anomaly_flag`'s DMA-level rule. Trained on `avg_night_flow_lpm` and `night_flow_ratio` (current night flow ÷ trailing 14-day per-meter baseline) — see `src/ml/features/leak_detection_features.py`.

**demand_forecasting_model** — Gradient-boosted regression predicting next-day DMA-level `metered_consumption_liters` from lag/calendar features (yesterday's and last week's consumption, trailing 7-day average, day of week). One pooled model across all DMAs, with `dma_id` as a feature — see `src/ml/features/demand_forecasting_features.py`.

**anomaly_detection_model** — Unsupervised (IsolationForest), one model per `meter_type` segment, scoring consumption relative to each meter's own baseline plus device-health signals (battery, reading count). Catches usage *drops* (a stuck or bypassed meter) that `usage_anomaly_flag`'s upper-bound rule cannot.

**predictive_maintenance_model** — Gradient-boosted classifier predicting whether a meter's battery will cross the low-battery threshold (15%) within the next 30 days, from the current battery level, a 14-day battery trend slope, and meter age. Predicts "battery will get low," not "meter will fail" — there is no real historical failure/replacement log in this platform to train an actual failure model against; see ADR-0012.

## Reading this glossary

Every model above is a **proxy or narrower-than-it-sounds claim, clearly labeled as such** — this platform is a demonstration/development environment with synthetic data, and its ML models and NRW figures should be described to a user with the same caveats documented here, not presented as production-audited numbers.
