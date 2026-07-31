from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounding box in image pixel coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
        }


@dataclass(frozen=True, slots=True)
class PpeDetection:
    """A single PPE detection normalized for downstream scoring."""

    item: str
    confidence: float
    bounding_box: BoundingBox
    class_id: int | None = None
    raw_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "item": self.item,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box.to_dict(),
        }
        if self.class_id is not None:
            payload["class_id"] = self.class_id
        if self.raw_label is not None:
            payload["raw_label"] = self.raw_label
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class PpeDetectionBatch:
    """The structured result returned by the PPE agent."""

    detections: list[PpeDetection]
    source_image: str | None = None
    model_name: str | None = None
    model_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": [detection.to_dict() for detection in self.detections],
            "source_image": self.source_image,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "created_at": self.created_at.isoformat(),
        }
