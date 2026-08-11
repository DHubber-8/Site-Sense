# Heat Compliance Alert Agent

This module checks today's forecast maximum temperature for a site city and maps it to the Section 2 compliance tiers in `taxonomy/heat_thresholds.md`.

## Contract

- Input: a site city plus a weather client that can fetch today's forecast max temperature.
- Output: a structured batch with the forecast summary and zero or one compliance alerts.
- Levels: `Level 1`, `Level 2`, `Level 3` only when the temperature crosses the Section 2 thresholds.
- Below 35°C: the batch still returns the forecast summary, but `alerts` is empty.

## Default weather client

The default client uses Open-Meteo's free geocoding and forecast APIs. It geocodes the site city first, then reads today's `temperature_2m_max` value directly from the daily forecast response.

No API key is required. The client keeps the provider details isolated behind the weather-client interface.

## Example

```python
from agents.heat_detection import HeatComplianceAlertAgent

agent = HeatComplianceAlertAgent(site_city="Shanghai")
batch = agent.assess()
print(batch.to_dict())
```

## Notes

- This is a forecast-based compliance check, not a WBGT or thermal-camera pipeline.
- The output is designed to feed downstream scoring and alert routing as structured data, not free text.