from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.alert_routing.schema import RoutedAlert
from agents.logging import LoggingAgent
from agents.risk_scoring.schema import RiskAssessment, Severity

_PRE_MIGRATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    severity INTEGER NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    zone TEXT,
    recommended_actions TEXT NOT NULL,
    source_detail TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    routed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL
)
"""

_PRE_EVIDENCE_IMAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    severity INTEGER NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    zone TEXT,
    recommended_actions TEXT NOT NULL,
    source_detail TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    requires_review INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL,
    routed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL
)
"""


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
        requires_review: bool = False,
        evidence_image: str | None = None,
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
            requires_review=requires_review,
            evidence_image=evidence_image,
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

    def test_record_persists_requires_review_flag(self) -> None:
        routed_alert = self._routed_alert(Severity.MINOR, "ppe", requires_review=True)

        self.store.record(routed_alert)
        recent = self.store.recent()

        self.assertTrue(recent[0].routed_alert.assessment.requires_review)

    def test_record_persists_evidence_image_path(self) -> None:
        routed_alert = self._routed_alert(
            Severity.CRITICAL,
            "ppe",
            evidence_image="data/sample_images/image1006.jpg",
        )

        self.store.record(routed_alert)
        recent = self.store.recent()

        self.assertEqual(
            recent[0].routed_alert.assessment.evidence_image,
            "data/sample_images/image1006.jpg",
        )

    def test_record_persists_no_evidence_image_for_heat_sources(self) -> None:
        routed_alert = self._routed_alert(Severity.MODERATE, "heat_wbgt")

        self.store.record(routed_alert)
        recent = self.store.recent()

        self.assertIsNone(recent[0].routed_alert.assessment.evidence_image)

    def test_evidence_image_column_migrates_onto_an_older_database(self) -> None:
        """A database created before evidence_image existed (but after requires_review) must
        gain the column automatically, the same way requires_review itself was added."""
        database_path = Path(self.temporary_directory.name) / "pre_evidence_image.db"
        connection = sqlite3.connect(database_path)
        connection.execute(_PRE_EVIDENCE_IMAGE_SCHEMA)
        connection.commit()
        connection.close()

        store = LoggingAgent(database_path)
        store.record(
            self._routed_alert(
                Severity.CRITICAL,
                "ppe",
                evidence_image="data/sample_images/image1006.jpg",
            )
        )

        self.assertEqual(
            store.recent()[0].routed_alert.assessment.evidence_image,
            "data/sample_images/image1006.jpg",
        )

    def test_concurrent_instantiation_against_a_pre_migration_database_does_not_crash(
        self,
    ) -> None:
        """Two LoggingAgents constructed at the same moment against a database still on the
        old (pre-requires_review) schema must not race on the ALTER TABLE migration."""
        database_path = Path(self.temporary_directory.name) / "pre_migration.db"
        connection = sqlite3.connect(database_path)
        connection.execute(_PRE_MIGRATION_SCHEMA)
        connection.commit()
        connection.close()

        errors: list[BaseException] = []

        def construct_agent() -> None:
            try:
                LoggingAgent(database_path)
            except (
                BaseException
            ) as exc:  # noqa: BLE001 - capturing for the assertion below
                errors.append(exc)

        threads = [threading.Thread(target=construct_agent) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])

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
