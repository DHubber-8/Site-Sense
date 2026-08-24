from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from agents.heat_detection.schema import (
    HeatComplianceAlert,
    HeatComplianceAlertBatch,
    WBGTRiskAlert,
    WBGTRiskBatch,
)
from agents.ppe_detection.schema import BoundingBox, PpeDetection, PpeDetectionBatch
from agents.risk_scoring import agent as risk_scoring
from agents.risk_scoring.schema import Severity


class RiskScoringSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scoring_agent = risk_scoring.RiskScoringAgent()
        self.reading_at = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)

    def test_ppe_scoring_matches_verified_model_labels(self) -> None:
        cases = [
            ("person", Severity.NONE),
            ("none", Severity.NONE),
            ("helmet", Severity.NONE),
            ("no_gloves", Severity.MODERATE),
            ("no_goggle", Severity.MODERATE),
            ("no_helmet", Severity.CRITICAL),
            ("no_boots", Severity.CRITICAL),
        ]

        for label, expected_severity in cases:
            with self.subTest(label=label):
                detection = PpeDetection(
                    item=label,
                    confidence=0.91,
                    bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0),
                )
                assessments = self.scoring_agent.assess(
                    PpeDetectionBatch(detections=[detection])
                )
                direct_assessments = [item for item in assessments if item.source == "ppe"]

                self.assertEqual(len(direct_assessments), 1)
                self.assertEqual(direct_assessments[0].severity, expected_severity)
                self.assertEqual(
                    direct_assessments[0].recommended_actions,
                    risk_scoring.PPE_RECOMMENDED_ACTIONS[expected_severity],
                )

    def test_ppe_scoring_rejects_labels_not_in_real_model(self) -> None:
        removed_labels = [
            "chin_strap_unfastened",
            "vest_partially_covered",
            "damaged_ppe",
        ]

        for label in removed_labels:
            with self.subTest(label=label):
                detection = PpeDetection(
                    item=label,
                    confidence=0.91,
                    bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0),
                )

                with self.assertRaisesRegex(ValueError, rf"Unsupported PPE label: {label}"):
                    self.scoring_agent.assess(PpeDetectionBatch(detections=[detection]))

    def test_ppe_scoring_low_confidence_flags_for_human_review(self) -> None:
        detection = PpeDetection(
            item="helmet",
            confidence=0.49,
            bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0),
        )

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=[detection]))
        assessment = next(item for item in assessments if item.source == "ppe")

        self.assertTrue(assessment.requires_review)
        self.assertEqual(assessment.severity, Severity.MINOR)
        self.assertEqual(
            assessment.description,
            "Possible helmet — low confidence, flagged for site supervisor review",
        )

    def test_ppe_scoring_high_confidence_does_not_flag_for_review(self) -> None:
        detection = PpeDetection(
            item="no_helmet",
            confidence=0.91,
            bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0),
        )

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=[detection]))
        assessment = next(item for item in assessments if item.source == "ppe")

        self.assertFalse(assessment.requires_review)
        self.assertEqual(assessment.severity, Severity.CRITICAL)
        self.assertEqual(assessment.description, "PPE violation detected: no_helmet (critical severity)")

    def test_ppe_coverage_all_items_confirmed_worn_has_no_coverage_alerts(self) -> None:
        detections = [
            PpeDetection(item="helmet", confidence=0.95, bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0)),
            PpeDetection(item="gloves", confidence=0.93, bounding_box=BoundingBox(2.0, 3.0, 12.0, 13.0)),
            PpeDetection(item="vest", confidence=0.92, bounding_box=BoundingBox(3.0, 4.0, 13.0, 14.0)),
            PpeDetection(item="boots", confidence=0.90, bounding_box=BoundingBox(4.0, 5.0, 14.0, 15.0)),
            PpeDetection(item="goggles", confidence=0.91, bounding_box=BoundingBox(5.0, 6.0, 15.0, 16.0)),
        ]

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=detections))
        coverage_assessments = [item for item in assessments if item.source == "ppe_coverage"]

        self.assertEqual(coverage_assessments, [])
        self.assertEqual(risk_scoring.overall_coverage_tier(assessments), 4)

    def test_ppe_coverage_one_item_unaccounted_emits_one_minor_alert(self) -> None:
        detections = [
            PpeDetection(item="helmet", confidence=0.95, bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0)),
            PpeDetection(item="vest", confidence=0.92, bounding_box=BoundingBox(3.0, 4.0, 13.0, 14.0)),
            PpeDetection(item="boots", confidence=0.90, bounding_box=BoundingBox(4.0, 5.0, 14.0, 15.0)),
            PpeDetection(item="goggles", confidence=0.91, bounding_box=BoundingBox(5.0, 6.0, 15.0, 16.0)),
        ]

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=detections))
        coverage_assessments = [item for item in assessments if item.source == "ppe_coverage"]

        self.assertEqual(len(coverage_assessments), 1)
        self.assertEqual(coverage_assessments[0].label, "gloves")
        self.assertEqual(coverage_assessments[0].severity, Severity.MINOR)
        self.assertEqual(
            coverage_assessments[0].description,
            "Could not verify gloves - flag for manual check",
        )
        self.assertEqual(risk_scoring.overall_coverage_tier(assessments), 3)

    def test_ppe_coverage_unaccounted_vest_uses_minor_coverage_path(self) -> None:
        detections = [
            PpeDetection(item="helmet", confidence=0.95, bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0)),
            PpeDetection(item="gloves", confidence=0.93, bounding_box=BoundingBox(2.0, 3.0, 12.0, 13.0)),
            PpeDetection(item="boots", confidence=0.90, bounding_box=BoundingBox(4.0, 5.0, 14.0, 15.0)),
            PpeDetection(item="goggles", confidence=0.91, bounding_box=BoundingBox(5.0, 6.0, 15.0, 16.0)),
        ]

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=detections))
        coverage_assessments = [item for item in assessments if item.source == "ppe_coverage"]

        self.assertEqual(len(coverage_assessments), 1)
        self.assertEqual(coverage_assessments[0].label, "vest")
        self.assertEqual(coverage_assessments[0].severity, Severity.MINOR)
        self.assertEqual(
            coverage_assessments[0].description,
            "Could not verify vest - flag for manual check",
        )

        direct_ppe_assessments = [item for item in assessments if item.source == "ppe"]
        self.assertFalse(
            any(item.label == "no_vest" for item in direct_ppe_assessments),
            "model has no no_vest class; vest gap must be coverage-based",
        )
        self.assertEqual(risk_scoring.overall_coverage_tier(assessments), 3)

    def test_ppe_coverage_mixed_batch_rolls_up_tier_from_layer_1_results(self) -> None:
        detections = [
            PpeDetection(item="helmet", confidence=0.95, bounding_box=BoundingBox(1.0, 2.0, 11.0, 12.0)),
            PpeDetection(item="vest", confidence=0.92, bounding_box=BoundingBox(3.0, 4.0, 13.0, 14.0)),
            PpeDetection(item="goggles", confidence=0.91, bounding_box=BoundingBox(5.0, 6.0, 15.0, 16.0)),
            PpeDetection(item="no_gloves", confidence=0.89, bounding_box=BoundingBox(2.0, 3.0, 12.0, 13.0)),
        ]

        assessments = self.scoring_agent.assess(PpeDetectionBatch(detections=detections))
        self.assertEqual(len([item for item in assessments if item.source == "ppe_coverage"]), 1)
        self.assertEqual(risk_scoring.overall_coverage_tier(assessments), 3)

    def test_heat_compliance_scoring_maps_boundary_levels(self) -> None:
        cases = [
            ("Level 1", Severity.MINOR),
            ("Level 2", Severity.MODERATE),
            ("Level 3", Severity.CRITICAL),
        ]

        for level, expected_severity in cases:
            with self.subTest(level=level):
                alert = HeatComplianceAlert(
                    city="Synthetic Site",
                    forecast_date=date(2026, 8, 10),
                    forecast_max_temperature_c=35.0,
                    level=level,
                    title=f"Heat {level}",
                    threshold_min_c=35.0,
                    regulatory_actions=[f"regulatory {level}"],
                    ai_actions=[f"AI {level}"],
                )
                batch = HeatComplianceAlertBatch(
                    site_city="Synthetic Site",
                    forecast_date=date(2026, 8, 10),
                    forecast_max_temperature_c=35.0,
                    alerts=[alert],
                )

                assessments = self.scoring_agent.assess(batch)

                self.assertEqual(assessments[0].severity, expected_severity)
                self.assertEqual(
                    assessments[0].recommended_actions,
                    [f"regulatory {level}", f"AI {level}"],
                )

    def test_wbgt_scoring_maps_boundary_tiers(self) -> None:
        cases = [
            ("Normal", Severity.NONE),
            ("Caution", Severity.MINOR),
            ("High Risk", Severity.MODERATE),
            ("Extreme", Severity.CRITICAL),
        ]

        for level, expected_severity in cases:
            with self.subTest(level=level):
                alert = WBGTRiskAlert(
                    city="Synthetic Site",
                    reading_at=self.reading_at,
                    wbgt_c=28.0,
                    level=level,
                    title=f"WBGT {level}",
                    threshold_min_c=28.0,
                    regulatory_actions=[f"regulatory {level}"],
                    ai_actions=[f"AI {level}"],
                )
                batch = WBGTRiskBatch(
                    site_city="Synthetic Site",
                    reading_at=self.reading_at,
                    wbgt_c=28.0,
                    alerts=[alert],
                )

                assessments = self.scoring_agent.assess(batch)

                self.assertEqual(assessments[0].severity, expected_severity)
                self.assertEqual(
                    assessments[0].recommended_actions,
                    [f"regulatory {level}", f"AI {level}"],
                )

    def test_source_detail_preserves_original_detection_and_alert(self) -> None:
        detection = PpeDetection(
            item="no_helmet",
            confidence=0.93,
            bounding_box=BoundingBox(3.0, 4.0, 13.0, 14.0),
            class_id=7,
            raw_label="no_helmet",
            metadata={"camera": "synthetic-camera-1"},
        )
        detection_assessment = self.scoring_agent.assess(
            PpeDetectionBatch(detections=[detection])
        )[0]

        alert = WBGTRiskAlert(
            city="Synthetic Site",
            reading_at=self.reading_at,
            wbgt_c=32.1,
            level="Extreme",
            title="Extreme Heat Risk",
            threshold_min_c=32.0,
            regulatory_actions=["Move workers to shade"],
            ai_actions=["Suspend heavy outdoor work"],
            metadata={"simulation_mode": True},
        )
        alert_assessment = self.scoring_agent.assess(
            WBGTRiskBatch(
                site_city="Synthetic Site",
                reading_at=self.reading_at,
                wbgt_c=32.1,
                alerts=[alert],
            )
        )[0]

        self.assertEqual(detection_assessment.source_detail, detection.to_dict())
        self.assertEqual(alert_assessment.source_detail, alert.to_dict())


if __name__ == "__main__":
    unittest.main()
