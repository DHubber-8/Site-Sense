# PPE coverage tracking plan

## Goal
Add a two-layer PPE coverage model that keeps real alerts driven by per-item evidence while exposing a display-only summary tier for dashboards.

## Layer 1: per-item source of truth
- Evaluate each core item in the PPE model (`helmet`, `gloves`, `vest`, `boots`, `goggles`).
- Treat positive labels as `confirmed_worn`, negative labels as `confirmed_missing`, and absence of both as `unaccounted`.
- Emit `ppe_coverage` `Severity.MINOR` assessments only for `unaccounted` items.
- Keep existing direct `ppe` source mapping for negative detections unchanged.
- Ensure the vest gap remains coverage-only because the model has no `no_vest` label.

## Layer 2: derived summary tier
- Add `overall_coverage_tier(assessments: list[RiskAssessment]) -> int` as a pure read of layer-1 output.
- Count confirmed-worn items from the per-item results; do not independently re-check the raw detection batch.
- Return 1-4 tiers based only on the number of confirmed-worn items while preserving the requirement that `Advanced` means all five are present and none are missing or unaccounted.

## Validation
- Add smoke tests for all-worn, one unaccounted, vest-specific unaccounted, and a mixed status batch.
- Run the focused risk-scoring test file after the patch.
