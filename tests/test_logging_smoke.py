from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.alert_routing.schema import RoutedAlert
from agents.logging import LoggingAgent
from agents.risk_scoring.schema import RiskAssessment, Severity


class LoggingSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = LoggingAgent(Path(self.temporary_directory.name) / "records.db")
        self.timestamp = datetime.now(timezone.utc)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _routed_alert(
        self,
        severity: Severity,
        source: str,
        timestamp: datetime | None = None,
    ) -> RoutedAlert:
        timestamp = timestamp or self.timestamp
        assessment = RiskAssessment(
            source=source,
            severity=severity,
            label=severity.name,
            description="Synthetic logging test",
            zone=None,
            recommended_actions=["Test action"],
            source_detail={"synthetic": True, "source": source},
            assessed_at=timestamp,
        )
        return RoutedAlert(
            assessment=assessment,
            decision=(
                "notify" if severity.value >= Severity.MODERATE.value else "log_only"
            ),
            routed_at=timestamp,
        )

    def test_record_persists_generated_id_and_nested_alert(self) -> None:
        routed_alert = self._routed_alert(Severity.MINOR, "ppe")

        record = self.store.record(routed_alert)
        recent = self.store.recent()

        self.assertTrue(record.record_id)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].record_id, record.record_id)
        self.assertEqual(recent[0].routed_alert.to_dict(), routed_alert.to_dict())
        self.assertIsInstance(record.recorded_at, datetime)

    def test_query_methods_filter_varied_records(self) -> None:
        first = self.store.record(
            self._routed_alert(
                Severity.MINOR,
                "ppe",
                datetime(2026, 1, 10, tzinfo=timezone.utc),
            ),
            recorded_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
        second = self.store.record(
            self._routed_alert(
                Severity.CRITICAL,
                "heat_wbgt",
                datetime(2026, 2, 10, tzinfo=timezone.utc),
            ),
            recorded_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
        )
        third = self.store.record(
            self._routed_alert(
                Severity.CRITICAL,
                "ppe",
                datetime(2026, 3, 10, tzinfo=timezone.utc),
            ),
            recorded_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        )

        recent = self.store.recent(limit=2)
        critical = self.store.filter_by_severity(Severity.CRITICAL)
        ppe = self.store.filter_by_source("ppe")
        date_range = self.store.filter_by_date_range(
            datetime(2026, 1, 10, tzinfo=timezone.utc),
            datetime(2026, 2, 10, tzinfo=timezone.utc),
        )

        self.assertEqual(
            [item.record_id for item in recent], [third.record_id, second.record_id]
        )
        self.assertEqual(len(critical), 2)
        self.assertTrue(
            all(
                item.routed_alert.assessment.severity is Severity.CRITICAL
                for item in critical
            )
        )
        self.assertEqual(len(ppe), 2)
        self.assertTrue(
            all(item.routed_alert.assessment.source == "ppe" for item in ppe)
        )
        self.assertEqual(
            [item.record_id for item in date_range],
            [second.record_id, first.record_id],
        )

    def test_filter_by_date_range_is_inclusive(self) -> None:
        record = self.store.record(
            self._routed_alert(Severity.MODERATE, "heat_compliance")
        )
        start = record.recorded_at - timedelta(seconds=1)
        end = record.recorded_at + timedelta(seconds=1)

        matching = self.store.filter_by_date_range(start, end)
        outside = self.store.filter_by_date_range(
            record.recorded_at - timedelta(days=2),
            record.recorded_at - timedelta(days=1),
        )

        self.assertEqual([item.record_id for item in matching], [record.record_id])
        self.assertEqual(outside, [])


if __name__ == "__main__":
    unittest.main()
