from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from agents.alert_routing.schema import RoutedAlert
from agents.risk_scoring.schema import RiskAssessment, Severity

from .schema import LogRecord

_CREATE_RECORDS_TABLE = """
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


def _utc_iso(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.isoformat()


def _from_iso(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


@dataclass(slots=True)
class LoggingAgent:
    """Persist and query routed alerts in a SQLite database."""

    database_path: str | Path = Path("data/site_sense.db")

    def __post_init__(self) -> None:
        database = Path(self.database_path)
        database.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(_CREATE_RECORDS_TABLE)

    def record(
        self,
        routed_alert: RoutedAlert,
        recorded_at: datetime | None = None,
    ) -> LogRecord:
        """Persist one routed alert and return its generated record."""

        record = LogRecord(
            record_id=str(uuid4()),
            routed_alert=routed_alert,
            recorded_at=recorded_at or datetime.now(timezone.utc),
        )
        assessment = routed_alert.assessment
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO records (
                    record_id, source, severity, label, description, zone,
                    recommended_actions, source_detail, assessed_at, decision,
                    routed_at, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    assessment.source,
                    assessment.severity.value,
                    assessment.label,
                    assessment.description,
                    assessment.zone,
                    json.dumps(assessment.recommended_actions),
                    json.dumps(assessment.source_detail),
                    _utc_iso(assessment.assessed_at),
                    routed_alert.decision,
                    _utc_iso(routed_alert.routed_at),
                    _utc_iso(record.recorded_at),
                ),
            )
        return record

    def record_many(self, routed_alerts: Iterable[RoutedAlert]) -> list[LogRecord]:
        """Persist multiple routed alerts and return their generated records."""

        return [self.record(routed_alert) for routed_alert in routed_alerts]

    def recent(self, limit: int = 50) -> list[LogRecord]:
        """Return the most recently recorded alerts first."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        return self._query(
            "SELECT * FROM records ORDER BY recorded_at DESC LIMIT ?", (limit,)
        )

    def filter_by_severity(self, severity: Severity) -> list[LogRecord]:
        """Return all records with the requested severity."""

        return self._query(
            "SELECT * FROM records WHERE severity = ? ORDER BY recorded_at DESC",
            (severity.value,),
        )

    def filter_by_source(self, source: str) -> list[LogRecord]:
        """Return all records from the requested risk source."""

        return self._query(
            "SELECT * FROM records WHERE source = ? ORDER BY recorded_at DESC",
            (source,),
        )

    def filter_by_date_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[LogRecord]:
        """Return records recorded within the inclusive UTC date-time range."""

        clauses: list[str] = []
        parameters: list[str] = []
        if start is not None:
            clauses.append("recorded_at >= ?")
            parameters.append(_utc_iso(start))
        if end is not None:
            clauses.append("recorded_at <= ?")
            parameters.append(_utc_iso(end))

        query = "SELECT * FROM records"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY recorded_at DESC"
        return self._query(query, tuple(parameters))

    def _query(self, query: str, parameters: tuple[object, ...]) -> list[LogRecord]:
        with self._connection() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, parameters).fetchall()
        return [self._record_from_row(row) for row in rows]

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> LogRecord:
        assessment = RiskAssessment(
            source=row["source"],
            severity=Severity(row["severity"]),
            label=row["label"],
            description=row["description"],
            zone=row["zone"],
            recommended_actions=json.loads(row["recommended_actions"]),
            source_detail=json.loads(row["source_detail"]),
            assessed_at=_from_iso(row["assessed_at"]),
        )
        routed_alert = RoutedAlert(
            assessment=assessment,
            decision=row["decision"],
            routed_at=_from_iso(row["routed_at"]),
        )
        return LogRecord(
            record_id=row["record_id"],
            routed_alert=routed_alert,
            recorded_at=_from_iso(row["recorded_at"]),
        )
