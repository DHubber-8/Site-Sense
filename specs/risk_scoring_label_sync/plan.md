# Risk Scoring PPE Label Sync Plan

## Goal
Align `PPE_SEVERITY_BY_LABEL` with the authoritative class labels in the trained YOLO checkpoint and update smoke tests accordingly.

## Scope
- `agents/risk_scoring/agent.py`
- `tests/test_risk_scoring_smoke.py`

## Verification Inputs
- Real checkpoint labels via `YOLO(...).names` from available `best.pt` artifacts.
- `taxonomy/ppe_severity.md` tiers for labels that genuinely exist.
- Construction-PPE dataset class semantics for `none` and `Person`.

## Implementation Plan
1. Remove dictionary keys not present in real model labels.
2. Add missing real model labels (normalized form as produced by PPE detection agent).
3. Reassign severity by taxonomy where applicable:
   - Missing PPE labels -> Critical/Moderate based on taxonomy examples.
   - Worn PPE, `person`, and generic `none` -> `Severity.NONE`.
4. Update description text for `none` to reflect model semantics.
5. Update risk-scoring smoke test cases to assert against verified labels/severities.

## Validation
- Run `python -m pytest tests/test_risk_scoring_smoke.py -q`.
- Summarize exact label diff (removed/added/severity changes) with reasons.
