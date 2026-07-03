"""Structured JSON logging for pipeline and job code.

CONTRIBUTING.md requires log records to be queryable (JSON, with `pipeline`,
`layer`, `run_id` fields) rather than bare `print()`, since this is how
Phase 8's Lakehouse Monitoring and on-call diagnosis consume them. This
module is the first concrete implementation of that requirement — Bronze
(Phase 3) predates it and has no application-level logging to retrofit
(Lakeflow's own event log already covers Bronze's single streaming read);
Silver (Phase 4) is the first place log records carry business-logic
meaning (e.g. quarantine volume per run) worth emitting explicitly.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "context", {}))
        return json.dumps(payload)


def get_logger(pipeline: str, layer: str, run_id: str) -> logging.LoggerAdapter:
    """Returns a logger that emits one JSON object per line to stdout, with
    `pipeline`, `layer`, and `run_id` attached to every record — the fields
    Lakehouse Monitoring/alerting (Phase 8) query on.

    `run_id` should be the Lakeflow pipeline update ID or Databricks Job run
    ID (available at runtime via the pipeline/job context), so log records
    can be correlated back to a specific run.
    """
    base_logger = logging.getLogger(f"smartmeter.{layer}.{pipeline}")
    if not base_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        base_logger.addHandler(handler)
        base_logger.setLevel(logging.INFO)
        base_logger.propagate = False
    context = {"pipeline": pipeline, "layer": layer, "run_id": run_id}
    return logging.LoggerAdapter(base_logger, {"context": context})
