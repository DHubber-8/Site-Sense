from __future__ import annotations

from pathlib import Path

import torch
import ultralytics
from ultralytics import YOLO


def _resolve_dataset_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / "construction-ppe.yaml",
        Path(ultralytics.__file__).resolve().parent
        / "cfg"
        / "datasets"
        / "construction-ppe.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Training dataset config not found. Tried: {', '.join(str(path) for path in candidates)}"
    )


def main() -> None:
    print(torch.cuda.is_available())
    print(
        torch.cuda.get_device_name(0)
        if torch.cuda.is_available()
        else "No GPU detected"
    )

    cuda_available = torch.cuda.is_available()
    device = 0 if cuda_available else "cpu"
    amp = cuda_available

    data_path = _resolve_dataset_path()
    model = YOLO("yolo26n.pt")
    model.train(
        data=str(data_path),
        epochs=100,
        imgsz=640,
        device=device,
        batch=16,
        workers=4,
        amp=amp,
    )


if __name__ == "__main__":
    main()
