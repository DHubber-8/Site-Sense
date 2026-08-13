from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class HeatComplianceAlert:
    """A single compliance alert derived from today's forecast maximum temperature."""

    city: str
    forecast_date: date
    forecast_max_temperature_c: float
    level: str
    title: str
    threshold_min_c: float
    threshold_max_c: float | None = None
    regulatory_actions: list[str] = field(default_factory=list)
    ai_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "city": self.city,
            "forecast_date": self.forecast_date.isoformat(),
            "forecast_max_temperature_c": self.forecast_max_temperature_c,
            "level": self.level,
            "title": self.title,
            "threshold_min_c": self.threshold_min_c,
            "regulatory_actions": list(self.regulatory_actions),
            "ai_actions": list(self.ai_actions),
        }
        if self.threshold_max_c is not None:
            payload["threshold_max_c"] = self.threshold_max_c
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class WBGTRiskAlert:
    """A WBGT risk classification derived from a simulated or sensor reading."""

    city: str
    reading_at: datetime
    wbgt_c: float
    level: str
    title: str
    threshold_min_c: float
    threshold_max_c: float | None = None
    regulatory_actions: list[str] = field(default_factory=list)
    ai_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "city": self.city,
            "reading_at": self.reading_at.isoformat(),
            "wbgt_c": self.wbgt_c,
            "level": self.level,
            "title": self.title,
            "threshold_min_c": self.threshold_min_c,
            "regulatory_actions": list(self.regulatory_actions),
            "ai_actions": list(self.ai_actions),
        }
        if self.threshold_max_c is not None:
            payload["threshold_max_c"] = self.threshold_max_c
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class HeatComplianceAlertBatch:
    """Structured forecast and alert output for the heat compliance agent."""

    site_city: str
    forecast_date: date
    forecast_max_temperature_c: float
    alerts: list[HeatComplianceAlert]
    weather_provider: str | None = None
    weather_source_url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "site_city": self.site_city,
            "forecast_date": self.forecast_date.isoformat(),
            "forecast_max_temperature_c": self.forecast_max_temperature_c,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "weather_provider": self.weather_provider,
            "weather_source_url": self.weather_source_url,
            "created_at": self.created_at.isoformat(),
        }
        return payload


@dataclass(slots=True)
class WBGTRiskBatch:
    """Structured WBGT risk output for simulated or pluggable sensor readings."""

    site_city: str
    reading_at: datetime
    wbgt_c: float
    alerts: list[WBGTRiskAlert]
    reading_source_name: str | None = None
    reading_source_url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "site_city": self.site_city,
            "reading_at": self.reading_at.isoformat(),
            "wbgt_c": self.wbgt_c,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "reading_source_name": self.reading_source_name,
            "reading_source_url": self.reading_source_url,
            "created_at": self.created_at.isoformat(),
        }
        return payload