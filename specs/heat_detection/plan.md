# Heat Compliance Alert Agent Plan

## Goal
Build a dedicated heat compliance alert agent under `agents/heat_detection/` that checks today's forecast maximum temperature for a site city and emits structured compliance alerts for Section 2 of `taxonomy/heat_thresholds.md`.

## Scope
- Evaluate the authoritative daily forecast maximum temperature for a site city.
- Classify the forecast into `Level 1`, `Level 2`, or `Level 3` compliance alerts using the Section 2 thresholds.
- Keep the agent focused on forecast-based compliance checks rather than WBGT or live thermal-camera logic.
- Support both the default Open-Meteo client and an OpenWeather fallback client without changing the calling contract.
- Return structured alert data so downstream scoring and alert routing can consume the output consistently.

## Implementation Steps
1. Define the heat compliance alert contract and output schema so the agent emits structured data rather than free text.
2. Add a normalized forecast-reading model that captures city, date, maximum temperature, source metadata, and provider details.
3. Implement weather clients for Open-Meteo and OpenWeather, keeping the interface isolated behind a shared protocol.
4. Classify forecast values against Section 2 thresholds and add statutory/regulatory actions and AI follow-up actions.
5. Expose the agent through the package API and ensure the batch output still includes the forecast summary even when no alert is triggered.
6. Add smoke tests covering threshold boundaries, fallback behavior, and the structured batch contract.

## Files
- `agents/heat_detection/__init__.py`
- `agents/heat_detection/agent.py`
- `agents/heat_detection/schema.py`
- `agents/heat_detection/README.md`
- `tests/test_heat_detection_smoke.py`
- `specs/heat_detection/plan.md`

## Risks
- The repository also contains a WBGT-based Section 1 module, so the forecast-compliance path must remain clearly separated from proxy/simulated heat-risk logic.
- `taxonomy/heat_thresholds.md` is protected and should only be read, not edited.
- Weather APIs may return incomplete, geocoded, or malformed payloads, so validation and error handling are important for reliable forecasts.
- The default client should remain provider-neutral to the calling code, but fallback logic must still preserve the source metadata used by downstream systems.
