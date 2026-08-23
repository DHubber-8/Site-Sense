from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agents.risk_scoring.schema import RiskAssessment


@dataclass(frozen=True, slots=True)
class RoutedAlert:
    """A risk assessment and the routing decision made for it."""

    assessment: RiskAssessment
    decision: str
    routed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment": self.assessment.to_dict(),
            "decision": self.decision,
            "routed_at": self.routed_at.isoformat(),
        }
