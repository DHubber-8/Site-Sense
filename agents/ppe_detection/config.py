from __future__ import annotations

from pathlib import Path

BASE_CHECKPOINT_PATH = Path("yolo26n.pt")
PPE_MODEL_PATH = "runs/detect/train/weights/best.pt"


def is_base_checkpoint(model_path: str | Path) -> bool:
    return Path(model_path).name == BASE_CHECKPOINT_PATH.name
