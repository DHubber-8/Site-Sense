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

    def test_ppe_scoring_covers_each_severity_tier(self) -> None:
        cases = [
            ("chin_strap_unfastened", Severity.MINOR),
            ("no_gloves", Severity.MODERATE),
            ("no_helmet", Severity.CRITICAL),
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

                self.assertEqual(len(assessments), 1)
                self.assertEqual(assessments[0].severity, expected_severity)
                self.assertEqual(
                    assessments[0].recommended_actions,
                    risk_scoring.PPE_RECOMMENDED_ACTIONS[expected_severity],
                )

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
