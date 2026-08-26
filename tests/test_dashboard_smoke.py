from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import dashboard.app as app
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
        return LogRecord(
            record_id=f"{source}-{label}-{severity.name}",
            routed_alert=routed,
            recorded_at=at,
        )

    def test_build_metrics_counts_severity_and_source_totals(self) -> None:
        records = [
            self._log_record(
                source="ppe",
                severity=Severity.CRITICAL,
                label="no_helmet",
                requires_review=True,
            ),
            self._log_record(
                source="ppe", severity=Severity.MODERATE, label="no_gloves"
            ),
            self._log_record(
                source="ppe_coverage",
                severity=Severity.MINOR,
                label="boots",
                requires_review=True,
            ),
            self._log_record(
                source="heat_wbgt",
                severity=Severity.CRITICAL,
                label="Extreme",
                requires_review=True,
            ),
            self._log_record(
                source="heat_compliance", severity=Severity.MINOR, label="Level 1"
            ),
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
            self._log_record(
                source="ppe",
                severity=Severity.MINOR,
                label="no_helmet",
                requires_review=True,
            ),
            self._log_record(
                source="ppe",
                severity=Severity.MINOR,
                label="gloves",
                requires_review=False,
            ),
            self._log_record(
                source="heat_wbgt",
                severity=Severity.CRITICAL,
                label="Extreme",
                requires_review=True,
            ),
        ]

        summary = summarize_active_alerts(records)

        self.assertEqual(summary["total_active"], 2)
        self.assertEqual(summary["review_items"][0].label, "no_helmet")
        self.assertEqual(summary["review_items"][1].label, "Extreme")

    def test_render_metric_card_omits_delta_and_renders_muted_caption(self) -> None:
        column = Mock()

        app._render_metric_card(column, "Active alerts", "4", "Require attention")

        # Value and caption go inside one bordered card so the caption reads as part of it.
        column.container.assert_called_once_with(border=True)
        card = column.container.return_value
        card.metric.assert_called_once_with("Active alerts", "4")
        self.assertGreaterEqual(card.markdown.call_count, 1)
        caption_markup = card.markdown.call_args[0][0]
        self.assertIn("metric-caption", caption_markup)
        self.assertIn("Require attention", caption_markup)


class DashboardPresentationSmokeTest(unittest.TestCase):
    """Presentation-layer checks: readable labels, no raw class tokens in details."""

    def _record(
        self,
        *,
        source: str,
        label: str,
        detail: dict,
        severity: Severity = Severity.MINOR,
        description: str = "",
    ) -> LogRecord:
        at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
        assessment = RiskAssessment(
            source=source,
            severity=severity,
            label=label,
            description=description,
            zone=None,
            recommended_actions=["Worker reminder"],
            source_detail=detail,
            assessed_at=at,
            requires_review=False,
        )
        routed = RoutedAlert(assessment=assessment, decision="notify", routed_at=at)
        return LogRecord(
            record_id=f"{source}-{label}", routed_alert=routed, recorded_at=at
        )

    def test_incident_name_distinguishes_violation_coverage_and_heat(self) -> None:
        violation = self._record(
            source="ppe",
            label="no_helmet",
            detail={"item": "no_helmet", "confidence": 0.9},
            severity=Severity.CRITICAL,
        )
        coverage = self._record(
            source="ppe_coverage",
            label="goggles",
            detail={"coverage_status": "unaccounted"},
        )
        heat = self._record(
            source="heat_wbgt", label="Caution", detail={"title": "Heat Caution"}
        )

        self.assertEqual(app._incident_name(violation), "Missing helmet")
        self.assertEqual(app._incident_name(coverage), "Eye protection not verified")
        self.assertEqual(app._incident_name(heat), "Heat Caution")

    def test_detail_rows_are_labelled_and_hide_internal_class_tokens(self) -> None:
        record = self._record(
            source="ppe",
            label="no_gloves",
            detail={
                "item": "no_gloves",
                "confidence": 0.82,
                "class_id": 4,
                "raw_label": "NO-Gloves",
                "bounding_box": {
                    "x_min": 10.0,
                    "y_min": 20.0,
                    "x_max": 60.0,
                    "y_max": 90.0,
                },
            },
        )

        rows = app._detail_rows(record)
        labels = [label for label, _ in rows]
        rendered = " ".join(f"{label} {value}" for label, value in rows)

        self.assertIn("Detected item", labels)
        self.assertIn("Image region", labels)
        for token in (
            "class_id",
            "raw_label",
            "NO-Gloves",
            "no_gloves",
            "bounding_box",
        ):
            self.assertNotIn(token, rendered)

    def test_detail_rows_keep_heat_readings_and_flag_proxy_source(self) -> None:
        record = self._record(
            source="heat_wbgt",
            label="Caution",
            detail={
                "title": "Heat Caution",
                "city": "Shenzhen",
                "reading_at": "2026-08-10T10:15:00+00:00",
                "wbgt_c": 28.1,
                "level": "Caution",
                "threshold_min_c": 28.0,
                "threshold_max_c": 30.0,
                "metadata": {"simulation_mode": True},
            },
        )

        rows = dict(app._detail_rows(record))

        self.assertEqual(rows["Site"], "Shenzhen")
        self.assertEqual(rows["WBGT reading"], "28.1 °C")
        self.assertEqual(rows["Threshold band"], "28–30 °C")
        self.assertIn("proxy", app._detail_note(record).lower())

    def test_readable_description_replaces_raw_ppe_token(self) -> None:
        record = self._record(
            source="ppe",
            label="no_gloves",
            detail={"item": "no_gloves", "confidence": 0.82},
            description="PPE violation detected: no_gloves (moderate severity)",
        )

        text = app._readable_description(record)

        self.assertNotIn("no_gloves", text)
        self.assertIn("missing gloves", text)

    def test_visible_alerts_reserves_slots_for_ppe_violations(self) -> None:
        heat = [
            self._record(
                source="heat_wbgt",
                label="Extreme",
                detail={"title": "Extreme Heat Risk"},
                severity=Severity.CRITICAL,
            )
            for _ in range(app.VISIBLE_ALERT_LIMIT * 2)
        ]
        violation = self._record(
            source="ppe",
            label="no_gloves",
            detail={"item": "no_gloves", "confidence": 0.6},
            severity=Severity.MINOR,
        )

        visible, total = app._visible_alerts([*heat, violation])

        self.assertLessEqual(len(visible), app.VISIBLE_ALERT_LIMIT)
        self.assertIn(violation, visible)
        self.assertEqual(total, len(heat) + 1)

    def test_visible_alerts_excludes_positive_and_coverage_records(self) -> None:
        positive = self._record(
            source="ppe", label="gloves", detail={"item": "gloves", "confidence": 0.9}
        )
        coverage = self._record(
            source="ppe_coverage",
            label="goggles",
            detail={"coverage_status": "unaccounted"},
        )
        violation = self._record(
            source="ppe",
            label="no_helmet",
            detail={"item": "no_helmet", "confidence": 0.9},
            severity=Severity.CRITICAL,
        )

        visible, total = app._visible_alerts([positive, coverage, violation])

        self.assertEqual(visible, [violation])
        self.assertEqual(total, 1)

    def test_reference_image_resolves_negative_labels_to_shared_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "goggles.png"
            reference.write_bytes(b"")
            with patch.object(app, "REFERENCE_IMAGE_DIR", Path(directory)):
                self.assertEqual(app._ppe_item_key("no_goggle"), "goggles")
                self.assertEqual(app._reference_image("goggles"), reference)
                self.assertIsNone(app._reference_image("helmet"))

    def test_severity_badge_uses_css_class_instead_of_inline_colors(self) -> None:
        markup = app._severity_badge("Critical")

        self.assertIn("sev-critical", markup)
        self.assertNotIn("style=", markup)


if __name__ == "__main__":
    unittest.main()
