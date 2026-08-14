# Requirements — Safety Monitoring & Response Agent

## Overview
An agent pipeline that monitors construction sites for two categories of risk:
1. **PPE compliance** (missing hard hats, unsafe proximity to machinery)
2. **Heat exhaustion / overwork risk** — using head/body temperature signals to flag workers showing signs of heat stress, relevant given high-heat working conditions in parts of China

Both feed into a shared risk-scoring and alert-routing system so site managers get one unified notification stream rather than two separate tools.

**Team:** E1, E2 (CS) · C (Civil Engineering)

---

## Functional Requirements

### PPE Detection
- FR1.1 — Detect presence/absence of required PPE (helmet, gloves, vest, boots, goggles) from site images — **implemented**, fine-tuned YOLO26 checkpoint (100 epochs on the Construction-PPE dataset), verified against real sample images. `no_boots` detection is unreliable due to limited training data (4 instances in the validation set) — documented as a known limitation, not a silent gap.
- FR1.2 — Detect unsafe worker proximity to machinery/hazard zones — **not implemented**, descoped in favor of getting core PPE detection production-ready

### Heat Exhaustion Detection
- FR2.1 — **Implemented as two paths**, per `taxonomy/heat_thresholds.md`:
  - Section 2 (compliance alerts): today's forecast maximum temperature for the site city, fetched from Open-Meteo (default, no API key required) or OpenWeather (fallback), classified into Level 1/2/3
  - Section 1 (WBGT risk): simulated temperature/humidity/wind-speed readings — the team decided against real thermal hardware or a proxy dataset, given time/resource constraints, in favor of a deterministic, seedable simulation that follows realistic time-of-day heat exposure patterns. **Clearly labeled as simulated in code and docs, not live sensor data.**
- FR2.2 — Flag individuals/zones whose estimated WBGT or forecast temperature exceeds a threshold associated with heat stress risk — implemented
- FR2.3 — Track duration of elevated readings, not just single-frame spikes — implemented via `_has_sustained_elevation()`, requiring multiple consecutive elevated readings within a configurable time window before escalating
- FR2.4 — **False-positive filtering**: implemented at the reading level (sustained-duration requirement above). Filtering against environmental confounds (e.g. direct sun exposure vs. genuine heat stress) is addressed by the simulation's realistic time-of-day modeling rather than sensor-calibration logic, since there is no physical sensor in this build.

### Risk Scoring & Alerting
- FR3.1 — Classify all detections (PPE + heat) into severity tiers (minor / moderate / critical) against a taxonomy defined with C's input
- FR3.2 — Route alerts by severity: log-only for minor, active notification for moderate/critical
- FR3.3 — Distinguish alert types clearly in the UI (a PPE violation and a heat-stress warning require different manager responses)

### Logging & Dashboard
- FR4.1 — Maintain a timestamped compliance/incident log across both detection categories
- FR4.2 — Dashboard shows current alerts, history, and — for heat monitoring — a trend view (is a worker's readings climbing over the shift)

---

## Non-Functional Requirements
- NFR1 — Detection pipeline runs within a few seconds per frame/image for a usable live demo
- NFR2 — Heat false-positive rate must be visibly reduced through at least one dedicated filtering pass — this is a named judging-relevant differentiator, not optional polish
- NFR3 — Severity thresholds (both PPE and heat) must be traceable to a real reference (safety code or heat-stress guidance), owned and documented by C
- NFR4 — UI must make the two alert categories (PPE vs heat) visually distinguishable at a glance

---

## Data Requirements
- Sample/public construction site images for PPE detection — using the Ultralytics Construction-PPE dataset (11 classes)
- Heat detection: **decided** — simulated data for the WBGT path (no real thermal hardware or proxy dataset), plus live weather-forecast data via Open-Meteo/OpenWeather for the compliance-alert path. Simulated readings are clearly labeled as such throughout the codebase and this document — no claim is made that this reflects live sensor hardware.
- Reference heat-stress thresholds — sourced from GBZ/T 229.3-2025 (WBGT) and China's high-temperature allowance guidance (compliance levels), documented in `taxonomy/heat_thresholds.md`
- Reference safety-code taxonomy for PPE severity — sourced from GB 2811-2019 and China's Law on Work Safety, documented in `taxonomy/ppe_severity.md`. **One cleanup item outstanding:** a duplicate/legacy file (`ppe_severity_ak.md`) with conflicting severity numbering still needs to be resolved by C.

---

## Team Ownership Summary
| Area | Owner |
|---|---|
| PPE detection pipeline | E1 |
| Heat detection pipeline + false-positive filtering logic | E1 + E2 |
| Risk-scoring, alert routing, logging | E2 |
| Dashboard | E2 (design input from C) |
| Safety code taxonomy + heat-stress thresholds | C |
| False-positive review / validation of both detection types | C |
| Pitch narrative + real-world cost/health framing | C |

---

## Key Risks
- **Heat detection uses simulated data, not real thermal hardware** — decided and implemented; must remain framed honestly as a proof-of-concept in the pitch, since judges will likely ask how this generalizes to real sensor hardware
- **PPE class imbalance** — the fine-tuned model performs well on "worn PPE" classes but weaker on some "missing PPE" classes, particularly `no_boots` (only 4 training instances). This is a data-volume limitation, not something further training epochs alone resolved — worth disclosing directly rather than overselling detection accuracy across all 11 classes
- False-positive filtering for heat is implemented via sustained-duration tracking (multiple consecutive elevated readings required before escalating) — this is the methodology judges are likely to probe, and it's ready to explain
- **Risk-scoring is now the critical path** — PPE and heat detection are both done; nothing downstream (alert routing, logging, dashboard) can proceed until risk-scoring exists. If this slips, cut dashboard scope before cutting risk-scoring/alert-routing, since those are the functional core