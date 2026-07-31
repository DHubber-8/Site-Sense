from __future__ import annotations

from pathlib import Path

PPE_MODEL_PATH = "yolo26n.pt"


def is_base_checkpoint(model_path: str | Path) -> bool:
    return Path(model_path).name == PPE_MODEL_PATH
