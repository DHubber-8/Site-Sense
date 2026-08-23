from __future__ import annotations

import unittest
from datetime import datetime, timezone

from agents.alert_routing import AlertRoutingAgent
from agents.risk_scoring.schema import RiskAssessment, Severity


class AlertRoutingSmokeTest(unittest.TestCase):
    def _assessment(self, severity: Severity) -> RiskAssessment:
        return RiskAssessment(
            source="synthetic",
            severity=severity,
            label=severity.name,
            description="Synthetic routing test",
            zone=None,
            recommended_actions=[],
            source_detail={"synthetic": True},
            assessed_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
        )

    def test_routes_each_severity_level(self) -> None:
        cases = [
            (Severity.NONE, None),
            (Severity.MINOR, "log_only"),
            (Severity.MODERATE, "notify"),
            (Severity.CRITICAL, "notify_urgent"),
        ]
        agent = AlertRoutingAgent()

        for severity, expected_decision in cases:
            with self.subTest(severity=severity):
                routed = agent.route(self._assessment(severity))

                if expected_decision is None:
                    self.assertIsNone(routed)
                else:
                    self.assertIsNotNone(routed)
                    assert routed is not None
                    self.assertEqual(routed.decision, expected_decision)
                    self.assertIsInstance(routed.routed_at, datetime)

    def test_routing_thresholds_are_configurable(self) -> None:
        agent = AlertRoutingAgent(
            notify_threshold=Severity.MINOR,
            notify_urgent_threshold=Severity.MODERATE,
        )

        self.assertEqual(
            agent.route(self._assessment(Severity.MINOR)).decision,
            "notify",
        )
        self.assertEqual(
            agent.route(self._assessment(Severity.MODERATE)).decision,
            "notify_urgent",
        )

    def test_route_many_omits_none_assessments(self) -> None:
        agent = AlertRoutingAgent()
        routed = agent.route_many([self._assessment(severity) for severity in Severity])

        self.assertEqual(
            [item.decision for item in routed],
            ["log_only", "notify", "notify_urgent"],
        )


if __name__ == "__main__":
    unittest.main()
