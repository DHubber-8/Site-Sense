from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agents.alert_routing.schema import RoutedAlert


@dataclass(frozen=True, slots=True)
class LogRecord:
    """A persisted routed alert with its storage identity and timestamp."""

    record_id: str
    routed_alert: RoutedAlert
    recorded_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "routed_alert": self.routed_alert.to_dict(),
            "recorded_at": self.recorded_at.isoformat(),
        }
