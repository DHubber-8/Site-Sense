"""Data-access layer for the dashboard: the LoggingAgent I/O boundary and record filtering.

Kept separate from dashboard/app.py's rendering code so the two concerns (reading records vs.
presenting them) can be reasoned about and changed independently.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from agents.logging import LoggingAgent
from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import Severity

DATABASE_PATH = str(PROJECT_ROOT / "data" / "site_sense.db")
HEAT_TAXONOMY_PATH = PROJECT_ROOT / "taxonomy" / "heat_thresholds.md"
SOURCE_LABELS = {
    "ppe": "PPE",
    "ppe_coverage": "PPE coverage",
    "heat_compliance": "Heat compliance",
    "heat_wbgt": "Heat exposure",
}
STATUS_LABELS = {
    "active": "Active",
    "acknowledged": "Acknowledged",
    "resolved": "Resolved",
}
MONITORED_SOURCES = {"ppe", "ppe_coverage", "heat_compliance", "heat_wbgt"}


@st.cache_resource(show_spinner=False)
def _agent() -> LoggingAgent:
    """One LoggingAgent per process, not one per call.

    LoggingAgent.__post_init__ opens a connection, runs CREATE TABLE IF NOT EXISTS, and checks
    for pending schema migrations — cheap once, wasteful re-run on every Streamlit script rerun
    (every filter change, every incident expand). Caching the agent itself is enough: each query
    still opens its own short-lived sqlite3 connection, so this doesn't share connections across
    threads, only the one-time setup work.
    """
    return LoggingAgent(DATABASE_PATH)


def _latest_record() -> LogRecord | None:
    records = _agent().recent(limit=1)
    return records[0] if records else None


def _assessment(record: LogRecord):
    return record.routed_alert.assessment


def _reporting_sources(records: list[LogRecord]) -> set[str]:
    return {
        _assessment(record).source
        for record in records
        if _assessment(record).source in MONITORED_SOURCES
        if not (_assessment(record).source_detail or {}).get("synthetic")
    }


def _wbgt_high_risk_threshold() -> float:
    try:
        taxonomy = HEAT_TAXONOMY_PATH.read_text(encoding="utf-8")
    except OSError:
        return 30.0
    match = re.search(r"Risk Level: High Risk \(WBGT:\s*([0-9.]+)", taxonomy)
    return float(match.group(1)) if match else 30.0


def _query_records(
    *,
    severity: str = "All severities",
    source: str = "All categories",
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LogRecord]:
    agent = _agent()
    records = (
        agent.filter_by_date_range(start, end)
        if start is not None or end is not None
        else agent.recent(limit=200)
    )
    record_sets = [{record.record_id for record in records}]
    by_id = {record.record_id: record for record in records}
    if severity != "All severities":
        matches = agent.filter_by_severity(Severity[severity.upper()])
        record_sets.append({record.record_id for record in matches})
        by_id.update({record.record_id: record for record in matches})
    if source != "All categories":
        source_key = next(
            key for key, label in SOURCE_LABELS.items() if label == source
        )
        matches = agent.filter_by_source(source_key)
        record_sets.append({record.record_id for record in matches})
        by_id.update({record.record_id: record for record in matches})
    matching = set.intersection(*record_sets)
    return sorted(
        (
            by_id[record_id]
            for record_id in matching
            if not (_assessment(by_id[record_id]).source_detail or {}).get("synthetic")
        ),
        key=lambda record: record.recorded_at,
        reverse=True,
    )


def _today_records() -> list[LogRecord]:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    records = _agent().filter_by_date_range(start=start, end=now)
    return [
        record
        for record in records
        if not (_assessment(record).source_detail or {}).get("synthetic")
    ]
