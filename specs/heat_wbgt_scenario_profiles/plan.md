# WBGT Scenario Profiles Plan

## Goal
Extend `SimulatedWBGTReadingSource` to support named deterministic scenario profiles for workday trace generation while preserving backward compatibility.

## Scope
- File impact:
  - `agents/heat_detection/wbgt_risk.py`
  - `tests/test_wbgt_risk_smoke.py`
- No taxonomy edits.

## Design
1. Add scenario-aware simulation path:
   - Keep current sinusoidal behavior as `baseline` (unchanged defaults).
   - Introduce deterministic scenario modifiers for:
     - `direct_sun_accumulation`
     - `brief_spike`
     - `fatigue_partial_recovery`
2. Add `scenario: str = "baseline"` to `generate_workday_trace()`.
3. Validate scenario names and raise `ValueError` for unsupported profiles.
4. Keep seed/city/date determinism by reusing existing seeded profile generation.
5. Keep `get_reading()` baseline behavior unchanged to avoid impacting existing agent/test behavior.

## Verification
- Run targeted tests for WBGT simulator/risk behavior.
- Add tests for:
  - determinism with scenario traces,
  - shape/risk characteristics per scenario,
  - brief spike not becoming sustained alert,
  - invalid scenario validation.
