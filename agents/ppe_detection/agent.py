from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from PIL import Image

from .config import PPE_MODEL_PATH, is_base_checkpoint
from .schema import BoundingBox, PpeDetection, PpeDetectionBatch


def _normalize_label(label: str) -> str:
    return label.strip().lower().replace(" ", "_").replace("-", "_")


def _load_image(image: str | Path | Image.Image) -> tuple[Any, str | None]:
    if isinstance(image, Image.Image):
        return image.convert("RGB"), None

    image_path = Path(image)
    with Image.open(image_path) as opened_image:
        return opened_image.convert("RGB"), str(image_path)


def _resolve_label(names: Any, class_id: int) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))

    if isinstance(names, list) and 0 <= class_id < len(names):
        return str(names[class_id])

    return str(class_id)


def _extract_coordinates(box: Any) -> list[float]:
    coordinates = getattr(box, "xyxy", [])
    if coordinates is None or len(coordinates) == 0:
        raise ValueError("YOLO box is missing xyxy coordinates")

    first_coordinates = coordinates[0]
    if hasattr(first_coordinates, "tolist"):
        return [float(value) for value in first_coordinates.tolist()]

    return [float(value) for value in first_coordinates]


@dataclass(slots=True)
class PpeDetectionAgent:
    """YOLO-backed PPE detection agent for construction site images."""

    model_path: str | Path = PPE_MODEL_PATH
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    device: str | None = None
    class_aliases: dict[str, str] = field(default_factory=dict)
    model_override: Any | None = None
    model_loader: Callable[[], Any] | None = None
    _model: Any | None = field(default=None, init=False, repr=False)

    def _load_model(self) -> Any:
        if self.model_override is not None:
            return self.model_override

        if self.model_loader is not None:
            self._model = self.model_loader()
            return self._model

        if self._model is not None:
            return self._model

        model_path = Path(self.model_path)
        if not model_path.exists() and not is_base_checkpoint(model_path):
            raise FileNotFoundError(f"PPE model checkpoint not found: {model_path}")

        try:
            from ultralytics import YOLO
        except (
            ImportError
        ) as exc:  # pragma: no cover - exercised in environments without ultralytics
            raise RuntimeError(
                "ultralytics is required for PPE detection. Install project dependencies first."
            ) from exc

        try:
            self._model = YOLO(str(self.model_path))
        except (
            Exception
        ) as exc:  # pragma: no cover - depends on ultralytics runtime behavior
            raise RuntimeError(
                f"Failed to load PPE model checkpoint: {self.model_path}"
            ) from exc

        return self._model

    def detect(self, image: str | Path | Image.Image) -> PpeDetectionBatch:
        model = self._load_model()
        loaded_image, source_image = _load_image(image)

        predictions = model.predict(
            source=loaded_image,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False,
        )

        detections: list[PpeDetection] = []
        for prediction in predictions:
            names = getattr(prediction, "names", {})
            boxes = getattr(prediction, "boxes", [])
            for box in boxes:
                class_id = int(box.cls.item())
                raw_label = _resolve_label(names, class_id)
                normalized_label = _normalize_label(raw_label)
                item = self.class_aliases.get(
                    raw_label,
                    self.class_aliases.get(normalized_label, normalized_label),
                )
                coordinates = _extract_coordinates(box)
                detections.append(
                    PpeDetection(
                        item=item,
                        confidence=float(box.conf.item()),
                        bounding_box=BoundingBox(
                            x_min=float(coordinates[0]),
                            y_min=float(coordinates[1]),
                            x_max=float(coordinates[2]),
                            y_max=float(coordinates[3]),
                        ),
                        class_id=class_id,
                        raw_label=raw_label,
                    )
                )

        return PpeDetectionBatch(
            detections=detections,
            source_image=source_image,
            model_name=model.__class__.__name__,
            model_path=str(self.model_path),
        )

    def detect_many(
        self, images: Iterable[str | Path | Image.Image]
    ) -> list[PpeDetectionBatch]:
        return [self.detect(image) for image in images]
