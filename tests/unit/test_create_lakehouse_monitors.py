"""Unit tests for src/jobs/create_lakehouse_monitors.py's idempotency
logic, using a fake workspace client (no live Databricks workspace
required — see MONITORED_TABLES for what a real run targets)."""

from __future__ import annotations

from src.jobs.create_lakehouse_monitors import create_or_update_monitor


class _FakeQualityMonitors:
    def __init__(self, existing_tables):
        self.existing_tables = set(existing_tables)
        self.create_calls = []

    def get(self, table_name):
        if table_name not in self.existing_tables:
            raise ValueError(f"Monitor not found for {table_name}")
        return {"table_name": table_name}

    def create(self, **kwargs):
        self.create_calls.append(kwargs)


class _FakeWorkspaceClient:
    def __init__(self, existing_tables=()):
        self.quality_monitors = _FakeQualityMonitors(existing_tables)


def test_create_or_update_monitor_creates_when_absent():
    client = _FakeWorkspaceClient(existing_tables=[])

    create_or_update_monitor(client, "smartmeter_dev.silver.meter_readings", "reading_timestamp")

    assert len(client.quality_monitors.create_calls) == 1
    call = client.quality_monitors.create_calls[0]
    assert call["table_name"] == "smartmeter_dev.silver.meter_readings"
    assert call["output_schema_name"] == "smartmeter_dev.silver"
    assert call["time_series"].timestamp_col == "reading_timestamp"


def test_create_or_update_monitor_skips_when_already_exists():
    client = _FakeWorkspaceClient(existing_tables=["smartmeter_dev.gold.daily_usage"])

    create_or_update_monitor(client, "smartmeter_dev.gold.daily_usage", "reading_date")

    assert client.quality_monitors.create_calls == []
