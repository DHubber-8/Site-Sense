# Heat Detection Agents

This folder contains the Section 2 temperature-compliance agent and the Section 1 WBGT risk module.

## Important: simulated-only output

The WBGT module in this folder is a deterministic simulation, not a live sensor feed. The readings are synthetic proxy data only. They are intended for testing, design, and pipeline validation and must not be described as live thermal-camera or WBGT-device data.

## Section 2 forecast compliance agent

This module checks today's forecast maximum temperature for a site city and maps it to the Section 2 compliance tiers in `taxonomy/heat_thresholds.md`.

### Contract

- Input: a site city plus a weather client that can fetch today's forecast max temperature.
- Output: a structured batch with the forecast summary and zero or one compliance alerts.
- Levels: `Level 1`, `Level 2`, `Level 3` only when the temperature crosses the Section 2 thresholds.
- Below 35°C: the batch still returns the forecast summary, but `alerts` is empty.

### Default weather client

The default client uses Open-Meteo's free geocoding and forecast APIs. It geocodes the site city first, then reads today's `temperature_2m_max` value directly from the daily forecast response.

No API key is required. The client keeps the provider details isolated behind the weather-client interface.

### Example

```python
from agents.heat_detection import HeatComplianceAlertAgent

agent = HeatComplianceAlertAgent(site_city="Shanghai")
batch = agent.assess()
print(batch.to_dict())
```

### Notes

- This is a forecast-based compliance check, not a WBGT or thermal-camera pipeline.
- The output is designed to feed downstream scoring and alert routing as structured data, not free text.

## Section 1 WBGT risk module

The WBGT proxy module implements the Section 1 thresholds using a protocol-based reading source and simulated environmental inputs.

- This WBGT output is simulated proxy data only.
- The reading source is protocol-based so a real sensor can replace the simulator later without changing the rest of the pipeline.
- The simulator is seedable and produces a realistic daytime curve instead of random noise.
- The values are clearly labeled as simulated in code comments and in this README to avoid implying live sensor data.