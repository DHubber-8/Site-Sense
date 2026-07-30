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
- FR1.1 — Detect presence/absence of required PPE (hard hats at minimum; harness/vest as stretch goals) from site images
- FR1.2 — Detect unsafe worker proximity to machinery/hazard zones

### Heat Exhaustion Detection
- FR2.1 — Estimate head/body surface temperature from available imaging (thermal camera feed if accessible, or a documented proxy method if not — see Data Requirements)
- FR2.2 — Flag individuals whose estimated temperature exceeds a threshold associated with heat stress risk
- FR2.3 — Track duration of elevated readings, not just single-frame spikes — a worker briefly reading hot after walking through sun is different from sustained elevation
- FR2.4 — **False-positive filtering**: distinguish genuine physiological heat stress from environmental confounds — e.g. a hard hat or exposed skin heated by direct sun exposure, ambient temperature drift over the day, camera calibration drift. This is treated as a first-class problem, not an afterthought.

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
- Sample/public construction site images for PPE detection (real thermal site data is unlikely to be available)
- For heat detection: either (a) a public thermal-imaging dataset as a proxy, or (b) a documented simulated/synthetic approach — e.g. estimating relative heat from RGB + a stated ambient-temperature model — **clearly labeled as a proxy method in the pitch**, since judges will likely ask how this generalizes to real thermal hardware
- Reference heat-stress thresholds (e.g. WBGT-style guidance or equivalent occupational heat exposure standards) — C's research task
- Reference safety-code taxonomy for PPE severity — C's research task

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
- **Heat detection is the highest-risk scope addition** — without real thermal camera access, the team must be explicit about using a proxy/simulated approach and framing it honestly as a proof-of-concept for when real thermal hardware is available on-site
- False-positive filtering for heat needs a genuine methodology (e.g. baseline calibration per shift, ambient-temp compensation) rather than an arbitrary threshold tweak — this is the part judges are most likely to probe
- If either detection pipeline is behind by end of Week 1, cut scope (e.g. hard hats only + heat-only, skip proximity detection) rather than pushing both simultaneously
