"""Build correct-PPE reference images from the real detection pipeline.

Runs the PPE detection agent over `data/sample_images/`, asks the risk scoring agent which
detections are compliant, and crops the highest-confidence compliant example of each PPE item
into `data/reference_ppe/`. The dashboard shows these on the Guidelines tab, in the PPE
response checklist, and in PPE incident details.

Nothing here is fabricated: every reference image is a crop of a frame the trained model
actually classified as correctly-worn PPE, and `manifest.json` records the provenance
(source frame, confidence, bounding box) for each one.

Compliance is decided by the agents, not by this script: an assessment counts as compliant
when the risk scoring agent returns `Severity.NONE` and does not flag it for review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

from agents.ppe_detection.agent import PpeDetectionAgent
from agents.ppe_detection.config import PPE_MODEL_PATH
from agents.risk_scoring.agent import RiskScoringAgent
from agents.risk_scoring.schema import Severity

SAMPLE_IMAGE_DIR = REPO_ROOT / "data" / "sample_images"
OUTPUT_DIR = REPO_ROOT / "data" / "reference_ppe"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
# PPE items the dashboard can illustrate. `person` and `none` are model bookkeeping classes,
# not protective equipment, so they are never used as a reference.
REFERENCE_ITEMS = ("helmet", "gloves", "vest", "boots", "goggles")
# Detection boxes are small relative to the 640px frames, so crop with context around the item
# rather than tight to the box, and never upscale a crop past its source resolution.
CROP_PADDING = 2.2
MIN_CROP_PX = 260
# Pixels at or below this luminance count as letterbox padding, not picture content.
LETTERBOX_LEVEL = 12
# Human-curated source frame per item, reviewed for legibility. These only *choose between*
# detections the scoring agent has already accepted as compliant — they never promote a
# non-compliant detection. Neither confidence nor box size predicts whether a crop actually
# reads as correct PPE: the largest compliant vest box is a mirrored press screenshot, and the
# most confident gloves box is an unreadable dark smudge. Drop an entry to fall back to the
# automatic largest-box pick.
PREFERRED_SOURCES = {
    "vest": "image714.jpeg",
    "gloves": "image771.jpg",
}


def _resolve_checkpoint() -> Path | None:
    """Prefer the configured checkpoint, else the newest trained one under runs/detect/."""
    configured = REPO_ROOT / PPE_MODEL_PATH
    if configured.exists():
        return configured
    candidates = sorted(
        (REPO_ROOT / "runs" / "detect").glob("*/weights/best.pt"),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _compliant_examples(checkpoint: Path) -> dict[str, dict[str, Any]]:
    """Best compliant detection per PPE item, as judged by the risk scoring agent.

    Among the detections the scoring agent accepts as compliant, pick the one with the largest
    bounding box rather than the highest confidence. Confidence measures how sure the model is,
    not how legible the crop will be — the highest-confidence helmet in this sample set is an
    77x82 px box that does not even include the worker's head.
    """
    agent = PpeDetectionAgent(model_path=checkpoint)
    scoring_agent = RiskScoringAgent()
    best: dict[str, dict[str, Any]] = {}

    for image_path in sorted(SAMPLE_IMAGE_DIR.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            batch = agent.detect(image_path)
        except Exception as exc:
            print(f"  Skipping {image_path.name}: detection failed ({exc})")
            continue

        for assessment in scoring_agent.assess(batch):
            if assessment.source != "ppe" or assessment.label not in REFERENCE_ITEMS:
                continue
            # The scoring agent decides compliance; this script only reads its verdict.
            if assessment.severity is not Severity.NONE or assessment.requires_review:
                continue
            detail = assessment.source_detail or {}
            box = detail.get("bounding_box")
            if box is None:
                continue
            area = (float(box["x_max"]) - float(box["x_min"])) * (
                float(box["y_max"]) - float(box["y_min"])
            )
            candidate = {
                "item": assessment.label,
                "source_image": image_path.name,
                "confidence": float(detail.get("confidence", 0.0)),
                "bounding_box": box,
                "area": area,
                "preferred": PREFERRED_SOURCES.get(assessment.label) == image_path.name,
            }
            current = best.get(assessment.label)
            if current is None or _outranks(candidate, current):
                best[assessment.label] = candidate
    return best


def _outranks(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """A curated frame wins; otherwise the larger box wins."""
    if candidate["preferred"] != current["preferred"]:
        return candidate["preferred"]
    return candidate["area"] > current["area"]


def _content_bounds(frame: Image.Image) -> tuple[int, int, int, int]:
    """Non-letterbox region of the frame.

    The sample images are padded to a square with black bars, and a crop that overlaps a bar
    renders as a reference image with a black stripe across it.
    """
    mask = frame.convert("L").point(lambda value: 255 if value > LETTERBOX_LEVEL else 0)
    return mask.getbbox() or (0, 0, frame.width, frame.height)


def _crop_box(
    box: dict[str, float],
    width: int,
    height: int,
    bounds: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Square crop centred on the detection, padded for context, clamped to real content."""
    left_limit, top_limit, right_limit, bottom_limit = bounds or (0, 0, width, height)
    x_min, y_min = float(box["x_min"]), float(box["y_min"])
    x_max, y_max = float(box["x_max"]), float(box["y_max"])
    centre_x, centre_y = (x_min + x_max) / 2, (y_min + y_max) / 2
    side = max(x_max - x_min, y_max - y_min) * CROP_PADDING
    side = max(side, MIN_CROP_PX)
    side = min(side, float(min(right_limit - left_limit, bottom_limit - top_limit)))
    left = min(max(centre_x - side / 2, float(left_limit)), right_limit - side)
    top = min(max(centre_y - side / 2, float(top_limit)), bottom_limit - side)
    return (round(left), round(top), round(left + side), round(top + side))


def _write_reference(example: dict[str, Any]) -> dict[str, Any]:
    source = SAMPLE_IMAGE_DIR / example["source_image"]
    with Image.open(source) as image:
        frame = image.convert("RGB")
        crop = _crop_box(
            example["bounding_box"],
            frame.width,
            frame.height,
            _content_bounds(frame),
        )
        frame.crop(crop).save(OUTPUT_DIR / f"{example['item']}.jpg", quality=92)
    return {
        "item": example["item"],
        "source_image": example["source_image"],
        "confidence": round(example["confidence"], 4),
        "crop_box": crop,
        "curated": example["preferred"],
    }


def main() -> None:
    checkpoint = _resolve_checkpoint()
    if checkpoint is None:
        print(
            f"No trained PPE checkpoint at {PPE_MODEL_PATH} or under runs/detect/."
            " Train the PPE model first (scripts/train_ppe_model.py)."
        )
        return
    print(f"Using PPE checkpoint: {checkpoint.relative_to(REPO_ROOT)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    examples = _compliant_examples(checkpoint)
    if not examples:
        print("No compliant PPE detections found in the sample images.")
        return

    entries = [
        _write_reference(examples[item]) for item in REFERENCE_ITEMS if item in examples
    ]
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps({"references": entries}, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"Wrote {len(entries)} reference images to {OUTPUT_DIR.relative_to(REPO_ROOT)}"
    )
    for entry in entries:
        print(
            f"  {entry['item']:8s} <- {entry['source_image']} "
            f"({entry['confidence']:.0%} confidence)"
        )
    missing = [item for item in REFERENCE_ITEMS if item not in examples]
    if missing:
        print(
            "  No confident compliant example in the sample set for: "
            + ", ".join(missing)
        )


if __name__ == "__main__":
    main()
