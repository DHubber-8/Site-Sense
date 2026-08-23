from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Iterable

from agents.risk_scoring.schema import RiskAssessment, Severity

from .schema import RoutedAlert


@dataclass(slots=True)
class AlertRoutingAgent:
    """Route risk assessments without delivering notifications."""

    notify_threshold: Severity = Severity.MODERATE
    notify_urgent_threshold: Severity = Severity.CRITICAL

    def __post_init__(self) -> None:
        if self.notify_threshold.value > self.notify_urgent_threshold.value:
            raise ValueError("notify_threshold cannot exceed notify_urgent_threshold")

    def route(self, assessment: RiskAssessment) -> RoutedAlert | None:
        """Return a routing decision, or None when no action is needed."""

        if assessment.severity is Severity.NONE:
            return None

        if assessment.severity.value >= self.notify_urgent_threshold.value:
            decision = "notify_urgent"
        elif assessment.severity.value >= self.notify_threshold.value:
            decision = "notify"
        else:
            decision = "log_only"

        return RoutedAlert(
            assessment=assessment,
            decision=decision,
            routed_at=datetime.now(timezone.utc),
        )

    def route_many(self, assessments: Iterable[RiskAssessment]) -> list[RoutedAlert]:
        """Route assessments and omit records requiring no action."""

        routed_alerts: list[RoutedAlert] = []
        for assessment in assessments:
            routed = self.route(assessment)
            if routed is not None:
                routed_alerts.append(routed)
        return routed_alerts
