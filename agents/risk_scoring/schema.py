from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(Enum):
    """Unified severity levels emitted by risk scoring."""

    NONE = 0
    MINOR = 1
    MODERATE = 2
    CRITICAL = 3


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """A normalized risk assessment for downstream agents."""

    source: str
    severity: Severity
    label: str
    description: str
    zone: str | None
    recommended_actions: list[str]
    source_detail: dict[str, Any]
    assessed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "severity": self.severity.value,
            "label": self.label,
            "description": self.description,
            "zone": self.zone,
            "recommended_actions": list(self.recommended_actions),
            "source_detail": dict(self.source_detail),
            "assessed_at": self.assessed_at.isoformat(),
        }
