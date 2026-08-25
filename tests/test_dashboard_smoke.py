from __future__ import annotations

import unittest
from datetime import datetime, timezone

from agents.alert_routing.schema import RoutedAlert
from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import RiskAssessment, Severity
from dashboard.logic import build_metrics, build_heat_timeline, summarize_active_alerts


class DashboardLogicSmokeTest(unittest.TestCase):
    def _log_record(
        self,
        *,
        source: str,
        severity: Severity,
        label: str,
        requires_review: bool = False,
        recorded_at: datetime | None = None,
    ) -> LogRecord:
        at = recorded_at or datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
        assessment = RiskAssessment(
            source=source,
            severity=severity,
            label=label,
            description="synthetic dashboard record",
            zone="zone-a",
            recommended_actions=["Review"],
            source_detail={"synthetic": True},
            assessed_at=at,
            requires_review=requires_review,
        )
        routed = RoutedAlert(assessment=assessment, decision="notify", routed_at=at)
        return LogRecord(record_id=f"{source}-{label}-{severity.name}", routed_alert=routed, recorded_at=at)

    def test_build_metrics_counts_severity_and_source_totals(self) -> None:
        records = [
            self._log_record(source="ppe", severity=Severity.CRITICAL, label="no_helmet", requires_review=True),
            self._log_record(source="ppe", severity=Severity.MODERATE, label="no_gloves"),
            self._log_record(source="ppe_coverage", severity=Severity.MINOR, label="boots", requires_review=True),
            self._log_record(source="heat_wbgt", severity=Severity.CRITICAL, label="Extreme", requires_review=True),
            self._log_record(source="heat_compliance", severity=Severity.MINOR, label="Level 1"),
        ]

        metrics = build_metrics(records)

        self.assertEqual(metrics["active_review_count"], 3)
        self.assertEqual(metrics["by_severity"]["Critical"], 2)
        self.assertEqual(metrics["by_severity"]["Moderate"], 1)
        self.assertEqual(metrics["by_severity"]["Minor"], 2)
        self.assertEqual(metrics["by_source"]["ppe"], 2)
        self.assertEqual(metrics["by_source"]["ppe_coverage"], 1)
        self.assertEqual(metrics["by_source"]["heat_wbgt"], 1)
        self.assertEqual(metrics["by_source"]["heat_compliance"], 1)

    def test_build_heat_timeline_keeps_wbgt_and_temperature_series(self) -> None:
        records = [
            self._log_record(
                source="heat_wbgt",
                severity=Severity.MINOR,
                label="Caution",
                requires_review=False,
                recorded_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
            ),
            self._log_record(
                source="heat_wbgt",
                severity=Severity.MODERATE,
                label="High Risk",
                requires_review=False,
                recorded_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
            ),
            self._log_record(
                source="heat_wbgt",
                severity=Severity.CRITICAL,
                label="Extreme",
                requires_review=True,
                recorded_at=datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc),
            ),
        ]
        records[0].routed_alert.assessment.source_detail["wbgt_c"] = 28.5
        records[0].routed_alert.assessment.source_detail["air_temperature_c"] = 30.0
        records[1].routed_alert.assessment.source_detail["wbgt_c"] = 31.2
        records[1].routed_alert.assessment.source_detail["air_temperature_c"] = 33.1
        records[2].routed_alert.assessment.source_detail["wbgt_c"] = 34.9
        records[2].routed_alert.assessment.source_detail["air_temperature_c"] = 38.0

        timeline = build_heat_timeline(records)

        self.assertEqual(len(timeline), 3)
        self.assertEqual(timeline[0]["wbgt_c"], 28.5)
        self.assertEqual(timeline[2]["air_temperature_c"], 38.0)

    def test_summarize_active_alerts_marks_requires_review_items(self) -> None:
        records = [
            self._log_record(source="ppe", severity=Severity.MINOR, label="no_helmet", requires_review=True),
            self._log_record(source="ppe", severity=Severity.MINOR, label="gloves", requires_review=False),
            self._log_record(source="heat_wbgt", severity=Severity.CRITICAL, label="Extreme", requires_review=True),
        ]

        summary = summarize_active_alerts(records)

        self.assertEqual(summary["total_active"], 2)
        self.assertEqual(summary["review_items"][0].label, "no_helmet")
        self.assertEqual(summary["review_items"][1].label, "Extreme")


if __name__ == "__main__":
    unittest.main()
