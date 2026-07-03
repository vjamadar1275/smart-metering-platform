"""Unit tests for src/jobs/silver_late_arrival_reconciliation.py's
pure-Python argument handling. The MERGE/I-O functions need a Unity
Catalog-backed Delta environment to exercise meaningfully and are left to
tests/integration/ (added when Phase 4's integration test harness lands);
this file covers the one piece of real logic that doesn't need Spark: the
lookback/watermark consistency guard.
"""

import pytest

from src.jobs.silver_late_arrival_reconciliation import parse_args, run


def test_parse_args_defaults():
    args = parse_args(["--catalog", "smartmeter_dev"])
    assert args.catalog == "smartmeter_dev"
    assert args.lookback_days == 3
    assert args.watermark_hours == 24


def test_parse_args_requires_catalog():
    with pytest.raises(SystemExit):
        parse_args([])


def test_run_rejects_lookback_shorter_than_watermark():
    args = parse_args(
        ["--catalog", "smartmeter_dev", "--lookback-days", "1", "--watermark-hours", "24"]
    )
    with pytest.raises(ValueError, match="must exceed"):
        # spark is never touched: the guard raises before any Spark I/O.
        run(spark=None, args=args)


def test_run_accepts_lookback_longer_than_watermark_before_touching_spark():
    args = parse_args(
        ["--catalog", "smartmeter_dev", "--lookback-days", "3", "--watermark-hours", "24"]
    )
    # A real run would proceed to call build_candidate_readings(spark, ...),
    # which fails immediately on spark=None — proves the guard passed
    # without asserting on downstream Spark/Delta behavior.
    with pytest.raises(AttributeError):
        run(spark=None, args=args)
