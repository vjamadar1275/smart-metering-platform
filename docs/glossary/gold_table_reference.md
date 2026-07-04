# Gold Table Reference

One entry per Gold table (Phase 5) — grain, key columns, and what question it answers. Source content for Phase 7's Vector Search KPI/glossary index, so the NL analytics agent can pick the right table for a user's question rather than guessing.

## gold.hourly_consumption

**Grain**: one row per (meter_id, hour_start). **Answers**: "how much did meter X use this hour/today?", intraday usage patterns, near-real-time dashboards. **Freshness**: streamed continuously from `silver.meter_readings` (see `src/pipelines/gold/gold_hourly_consumption.py`) — the lowest-latency Gold table. **Key columns**: `consumption_liters`, `avg_flow_rate_lpm`, `min_battery_pct`, `dma_id`, `customer_id`.

## gold.daily_usage

**Grain**: one row per (meter_id, reading_date). **Answers**: "how much did meter X use on day Y?", meter-level trend/anomaly questions, the base table most other Gold marts roll up from. **Freshness**: triggered/batch, refreshed daily (see `src/pipelines/gold/gold_daily_marts.py` and ADR-0011 for why this KPI is batch, not streaming, unlike `hourly_consumption`). **Key columns**: `consumption_liters`, `trailing_7d_avg_liters`, `usage_anomaly_flag`.

## gold.dma_analytics

**Grain**: one row per (dma_id, reading_date). **Answers**: "which DMA has the highest leak risk?", "what's our non-revenue water rate?" (proxy — see `kpi_glossary.md`), District Meter Area-level operational questions. **Key columns**: `metered_consumption_liters` (real), `estimated_supply_liters`/`non_revenue_water_pct` (proxy, ADR-0011), `avg_night_flow_lpm`/`night_flow_anomaly_flag` (real leak indicator).

## gold.customer_analytics

**Grain**: one row per (customer_id, reading_date). **Answers**: "is this customer's usage trending up or down?", billing-relevant customer-level questions. Rolled up from `gold.daily_usage`, not raw Silver. **Key columns**: `consumption_liters`, `rolling_30d_avg_liters`, `trend_direction` (INCREASING/DECREASING/STABLE/INSUFFICIENT_HISTORY), `high_usage_flag`.

## gold.operational_dashboard

**Grain**: one row per pipeline run (a snapshot, not a time series — don't ask it "trend over time" questions, use `gold.daily_usage`/`gold.dma_analytics` instead). **Answers**: "how many meters are active today?", "what's today's data-quality quarantine rate?" **Key columns**: `active_meter_count`, `quarantine_rate_pct`, `dma_leak_flag_count`.

## gold.executive_dashboard

**Grain**: one row per most-recently-complete day (also a snapshot mart, not a full time series). **Answers**: top-line business questions — total volume, systemwide NRW% (proxy), revenue-relevant volume by customer segment, high-usage customer count. **Key columns**: `total_consumption_liters`, `systemwide_nrw_pct` (proxy), `residential_liters`/`commercial_liters`/`industrial_liters`.

## Choosing a table

If a question is about a **specific meter or customer**, start with `gold.daily_usage` or `gold.customer_analytics`. If it's about a **DMA or leak/NRW**, use `gold.dma_analytics`. If it's a **top-line/executive** question, use `gold.executive_dashboard`. If it needs **hour-level granularity**, only `gold.hourly_consumption` has it. If it's about **right now** (not historical trend), the two dashboard snapshot tables are the right (and only sensible) source.
