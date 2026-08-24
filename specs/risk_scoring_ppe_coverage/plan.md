# PPE Coverage Check Plan

## Goal
Add a batch-level PPE coverage assessment in risk scoring to flag unaccounted core PPE items for manual review.

## Scope
- `agents/risk_scoring/agent.py`
- `tests/test_risk_scoring_smoke.py`

## Design
1. Keep existing per-detection `assess_ppe()` mapping unchanged for confirmed positive/negative labels.
2. Add a separate coverage function that evaluates core PPE pairs across the whole `PpeDetectionBatch`:
   - helmet / no_helmet
   - gloves / no_gloves
   - vest / (no negative class)
   - boots / no_boots
   - goggles / no_goggle
3. Emit one `RiskAssessment` (`source="ppe_coverage"`, `Severity.MINOR`) per unaccounted core item with description:
   - `Could not verify {item} — flag for manual check`
4. Add explicit inline comment that vest has no `no_vest` class in this model; vest misses can only be surfaced by coverage/unaccounted logic.
5. Update `RiskScoringAgent.assess()` for PPE batches to return both direct detection assessments and coverage assessments.

## Tests
- All core items confirmed worn -> no coverage alerts.
- One core item unaccounted -> one Minor coverage alert.
- Vest unaccounted -> one Minor coverage alert via coverage path.

## Validation
- Run `python -m pytest tests/test_risk_scoring_smoke.py -q`.
