from __future__ import annotations

from pathlib import Path

BASE_CHECKPOINT_PATH = Path("yolo26n.pt")
PPE_MODEL_PATH = "runs/detect/train-10/weights/best.pt"


def is_base_checkpoint(model_path: str | Path) -> bool:
    return Path(model_path).name == BASE_CHECKPOINT_PATH.name


def resolve_trained_checkpoint(repo_root: Path) -> Path | None:
    """Return a usable trained PPE checkpoint, preferring the configured path.

    Training runs land in `runs/detect/<run>/weights/best.pt` and `runs/` is gitignored, so
    the configured default is frequently absent on a fresh clone. Fall back to the most
    recently written trained checkpoint instead of silently seeding a heat-only demo.
    """
    configured = repo_root / PPE_MODEL_PATH
    if configured.exists():
        return configured
    candidates = sorted(
        (repo_root / "runs" / "detect").glob("*/weights/best.pt"),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None
