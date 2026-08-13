# WBGT Risk Module

This module provides a deterministic WBGT proxy for heat-risk workflows that need Section 1 thresholding from `taxonomy/heat_thresholds.md`.

## Contract

- Input: a city name plus a `WBGTReadingSource` implementation.
- Output: a structured batch with one WBGT risk classification and the underlying reading metadata.
- Levels: `Normal`, `Caution`, `High Risk`, `Extreme` using the WBGT thresholds in Section 1.

## Simulation notes

- The default source is a simulated proxy, not a live thermal-camera or sensor feed.
- Simulated readings are deterministic and seedable so tests can reproduce the same workday trace.
- The generator produces a realistic daytime pattern with gradual warming, a midday peak, and a break-period drop.

## Example

```python
from agents.heat_detection import WBGTRiskAgent

agent = WBGTRiskAgent(site_city="Shanghai")
batch = agent.assess()
print(batch.to_dict())
```

## Notes

- Use this module for proxy heat-risk simulation and later swap the reading source with a real sensor implementation.
- The module is intentionally structured so the reading source can change without changing the rest of the pipeline.