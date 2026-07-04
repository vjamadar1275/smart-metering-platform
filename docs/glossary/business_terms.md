# Business Terms

General water-utility terminology used throughout this platform's Gold layer, dashboards, and models — source content for Phase 7's Vector Search KPI/glossary index.

## DMA (District Meter Area)

A defined, hydraulically isolated section of a water distribution network with its own bulk metering boundary, used to localize leak detection and water-balance accounting. This platform models 20 DMAs (`DMA-001` through `DMA-020`, `reference.dim_dma`), each with a `zone`, `supply_source`, `population_served`, and `target_nrw_pct`.

## Non-revenue water (NRW)

Water that is produced/supplied but not billed to customers, due to real losses (leaks, pipe bursts), apparent losses (meter inaccuracy, theft), or unbilled authorized consumption (firefighting, flushing). Industry NRW rates commonly range 8-18%. In this platform, NRW is currently an **estimated proxy**, not a measured figure — see `kpi_glossary.md` and ADR-0011.

## Night flow / minimum night flow

The water flow observed during a utility's lowest-demand hours (typically 02:00-04:00), when legitimate customer usage is at its minimum. Sustained non-zero night flow beyond what a handful of always-on appliances (fridges, etc.) would produce is the classic signature of a leak — the basis for both `gold.dma_analytics.night_flow_anomaly_flag` and Phase 7's `leak_detection_model`.

## Meter types

`RESIDENTIAL`, `COMMERCIAL`, `INDUSTRIAL` (`reference.dim_meter.meter_type`). Consumption scale and variance differ enormously by type (an industrial meter's "normal" volume dwarfs a residential one's), which is why several Phase 7 models (`anomaly_detection_model`) are trained per-segment rather than pooled across all meters.

## Account types

`RESIDENTIAL`, `COMMERCIAL`, `INDUSTRIAL`, `UNKNOWN` (`reference.dim_customer.account_type`, carried through to Gold as `account_type`). `UNKNOWN` means the reading enriched against a meter with no matching `reference.dim_customer` row — itself a data-completeness signal, not just a missing label.

## Quarantine

Meter readings that failed a Silver validation rule (missing required field, implausible reading value, or an unknown meter not in `reference.dim_meter`) are never silently dropped; they're written to `quarantine.silver_meter_readings` with a `reason_code` documenting which rule failed. See ADR-0003 (Lakeflow Expectations) and `src/libs/quality/expectations.py`.

## Watermark / late arrival

Silver's streaming pipeline uses a 24-hour watermark on `reading_timestamp` to bound streaming state; a reading arriving more than 24 hours after it was taken (e.g. a meter reconnecting after an extended outage) is still captured — not dropped — by a nightly batch reconciliation job, not the streaming pipeline itself. See ADR-0010.

## SCD Type 2 (Slowly Changing Dimension)

The versioning scheme `reference.dim_meter` and `reference.dim_customer` use: a change (e.g. a meter reassigned to a new DMA) closes out the old row (`effective_end_date`, `is_current = false`) and inserts a new "current" version, so historical Gold aggregates still join to the dimension values that were actually in effect at the time. `reference.dim_dma` is intentionally Type 1 (overwrite in place) instead — DMA boundaries change rarely enough that history wasn't judged worth the complexity.
