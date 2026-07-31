# PPE Detection Agent Plan

## Goal
Build a dedicated PPE detection agent under `agents/ppe_detection/` that wraps a pretrained YOLO model fine-tuned for construction PPE and emits structured detections for downstream risk scoring.

## Scope
- Detect PPE items from site images, starting with hard-hat detection.
- Return structured detections with item label, confidence, and bounding box.
- Keep model loading configurable so different fine-tuned checkpoints can be swapped without changing call sites.
- Leave severity mapping and alert routing to downstream agents.

## Implementation Steps
1. Define a stable data schema for PPE detections and batches.
2. Implement a YOLO-backed inference wrapper with lazy model loading.
3. Normalize model outputs into the shared structured schema.
4. Add a small smoke-test entrypoint and documentation for the agent contract.

## Files
- `agents/ppe_detection/__init__.py`
- `agents/ppe_detection/schema.py`
- `agents/ppe_detection/agent.py`
- `agents/ppe_detection/README.md`
- `pyproject.toml`

## Risks
- The repo does not include a trained checkpoint, so the agent must fail clearly when the model path is missing.
- The project does not yet define canonical PPE class labels, so output normalization should remain configurable.
- Sample images are not present yet, so smoke tests may need to be added after fixtures land.