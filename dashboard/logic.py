from __future__ import annotations

from collections import Counter
from datetime import datetime

from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import Severity

SEVERITY_ORDER = ["Critical", "Moderate", "Minor"]
SOURCE_TYPES = ["ppe", "ppe_coverage", "heat_compliance", "heat_wbgt"]


def _severity_name(severity: Severity) -> str:
    if severity is Severity.CRITICAL:
        return "Critical"
    if severity is Severity.MODERATE:
        return "Moderate"
    return "Minor"


def build_metrics(records: list[LogRecord]) -> dict[str, object]:
    """Summarize active records for the manager dashboard."""
    by_severity = {level: 0 for level in SEVERITY_ORDER}
    by_source = {source: 0 for source in SOURCE_TYPES}
    active_review_count = 0

    for record in records:
        assessment = record.routed_alert.assessment
        by_severity[_severity_name(assessment.severity)] += 1
        by_source[assessment.source] = by_source.get(assessment.source, 0) + 1
        if assessment.requires_review:
            active_review_count += 1

    return {
        "active_review_count": active_review_count,
        "by_severity": by_severity,
        "by_source": by_source,
    }


def summarize_active_alerts(records: list[LogRecord]) -> dict[str, object]:
    """Return the subset of records requiring supervisor attention."""
    review_items = [
        record.routed_alert.assessment for record in records if record.routed_alert.assessment.requires_review
    ]
    return {
        "total_active": len(review_items),
        "review_items": review_items,
    }


def build_heat_timeline(records: list[LogRecord]) -> list[dict[str, object]]:
    """Convert heat_wbgt log entries into a time-based trend payload."""
    heat_records = [record for record in records if record.routed_alert.assessment.source == "heat_wbgt"]

    timeline: list[dict[str, object]] = []
    for record in sorted(heat_records, key=lambda item: item.recorded_at):
        assessment = record.routed_alert.assessment
        source_detail = assessment.source_detail or {}
        timeline.append(
            {
                "timestamp": record.recorded_at.isoformat(),
                "label": assessment.label,
                "severity": _severity_name(assessment.severity),
                "wbgt_c": float(source_detail.get("wbgt_c", 0.0)),
                "air_temperature_c": float(source_detail.get("air_temperature_c", 0.0)),
                "requires_review": assessment.requires_review,
            }
        )
    return timeline
