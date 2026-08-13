# WBGT Heat Risk Module Plan

## Goal
Build a new WBGT-based heat risk module under `agents/heat_detection/` that implements Section 1 of `taxonomy/heat_thresholds.md` while leaving the existing Section 2 forecast-based compliance agent intact.

## Scope
- Generate realistic simulated WBGT inputs from temperature, humidity, and wind speed.
- Make the simulation deterministic and seedable so tests can reproduce the same exposure pattern.
- Model realistic time-series behavior over a workday, including gradual daytime rise and brief recovery during breaks.
- Classify WBGT readings into Normal, Caution, High Risk, and Extreme using the Section 1 thresholds.
- Keep the existing Section 2 forecast-based agent unchanged and available alongside the new module.
- Clearly label the module as proxy/simulated data, not live thermal-camera input.

## Implementation Steps
1. Define the WBGT module boundary and structured output schema so simulated readings can be consumed by downstream agents.
2. Implement a deterministic generator for temperature, humidity, and wind speed that follows a realistic workday pattern instead of random noise.
3. Compute WBGT from the simulated inputs and classify readings against the Section 1 thresholds.
4. Expose the new module through package exports and document how it differs from the existing Section 2 compliance path.
5. Add smoke tests that verify determinism, realistic progression, and threshold boundaries.

## Files
- `agents/heat_detection/agent.py`
- `agents/heat_detection/schema.py`
- `agents/heat_detection/__init__.py`
- `agents/heat_detection/README.md`
- `tests/test_heat_detection_smoke.py`
- `specs/heat_wbgt/plan.md`

## Risks
- The repo currently has a working forecast-based heat agent, so the new WBGT module should be additive rather than a rewrite.
- `taxonomy/heat_thresholds.md` is protected and should only be read, not edited.
- The simulated data must remain clearly labeled as proxy data to avoid implying real thermal-camera support.
- If the WBGT schema is too tightly coupled to the current Section 2 forecast path, downstream integration could become confusing, so the module boundary should stay explicit.
