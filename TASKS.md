# Tasks — Safety Monitoring & Response Agent (3 weeks, 3-person team)

Team: **E1, E2** (CS) · **C** (Civil Engineering)
Legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Week 1 — Foundations & Scoping

### Repo & tooling
- [x] Init repo, add `AGENTS.md` with project conventions (agent folder structure, data schema rules, commit format) — **E2**
- [x] Set up base folder structure (see repo layout below) — **E2**
- [x] Add Copilot-specific config (`.github/agents/`, `.github/instructions/`, `.github/prompts/`) mirroring `AGENTS.md` conventions — **E2**
- [x] Run an Architect-mode session for the PPE detection agent, producing `/specs/ppe_detection/plan.md` — **E1**
- [x] Run an Architect-mode session for the heat detection agent, producing `/specs/heat_detection/plan.md` and `/specs/heat_wbgt/plan.md` — **E1** (backfilled after implementation, see Week 2 note)

### Research & taxonomy (C)
- [x] Research PPE safety codes → draft severity taxonomy (minor/moderate/critical) — **C** (merged)
- [x] Research heat-stress/heat-exhaustion occupational guidance → draft heat-severity thresholds — **C** (merged)
- [x] Decide + document the heat-detection data approach — **C + E1** — **decided: simulated data (WBGT path) + live weather forecast (compliance path), no real hardware**

### PPE pipeline (E1)
- [x] Evaluate pretrained PPE-detection models, select one — **E1** (YOLO26, fine-tuned on Construction-PPE dataset, 100 epochs)
- [x] Get detection running standalone on sample images — **E1** (fixture-based smoke test passing)

### Heat pipeline (E1 + E2)
- [x] Source or build a starter thermal/heat data source — **E1** (decided: simulated WBGT data, deterministic + seedable; weather forecast via Open-Meteo/OpenWeather for the compliance path)
- [x] Prototype the heat-reading extraction method — **E1** (both paths implemented and tested)

### End of Week 1 checkpoint
- [x] Team sync: confirm both detection approaches are technically viable before committing further — **All**

> **Week 1 closed out.** All detection foundations are in place; the project has moved into Week 2's core build.

---

## Week 2 — Core Build

### PPE + heat integration
- [x] Wire PPE detection agent into pipeline — **E1** (fine-tuned checkpoint verified against real sample images; `no_boots` detection documented as unreliable due to limited training data)
- [x] Wire heat detection agent into pipeline — **E1** (both compliance-alert and WBGT paths implemented)
- [x] Build false-positive filtering pass for heat readings — **E1** (sustained-duration tracking via `_has_sustained_elevation()`, requires multiple consecutive elevated readings before escalating)
- [x] Write integration contract documenting detection agent output shapes for risk-scoring — **E1** (`specs/system_design.md`, `specs/detection/detection_output_contract.md`)
- [x] Resolve duplicate PPE taxonomy file (`ppe_severity_ak.md` vs. `ppe_severity.md`) — **C** (removed)
- [x] Confirm WBGT 4-tier → 3-tier severity mapping (Normal/Caution/High Risk/Extreme → NONE/MINOR/MODERATE/CRITICAL) — **C** (agreed)

### Risk scoring & alerts
- [x] Build risk-scoring agent using C's PPE taxonomy — **E1** (took over from E2) — **label set needs verification against real model output, see below**
- [x] Build risk-scoring agent using C's heat thresholds (handles both Level 1/2/3 and Normal/Caution/High Risk/Extreme naming schemes) — **E1**
- [x] Build alert-routing agent (severity-based: log-only vs. active notification) — **E1**
- [x] Build compliance/incident logging store — **E1**
- [ ] **Fix:** `agents/risk_scoring/agent.py`'s `PPE_SEVERITY_BY_LABEL` includes labels (`chin_strap_unfastened`, `vest_partially_covered`, `damaged_ppe`) that don't match the trained model's actual output classes — verify against `model.names` on the real checkpoint and correct — **E1**
- [x] Resolve `specs/` duplicate plan files (`risk_scoring_plan.md`, `alert_routing_plan.md`, `logging_plan.md` each duplicate an existing `plan.md`) — **E1**

### Validation
- [x] Run first end-to-end test (image/data in → detections → scoring → alert → log) — **E1** (test exists, correctly skips in environments without the trained checkpoint present; needs a real run against `best.pt` to confirm it actually passes end-to-end)
- [ ] Review false positives/negatives from test run (both PPE and heat), adjust rules — **C**

### End of Week 2 checkpoint
- [~] Full pipeline runs end-to-end for both detection types — **All** — code complete, pending the label-verification fix above and one real (non-skipped) end-to-end run

---

## Week 3 — Integration, Polish, Pitch

### Refinement
- [ ] Tune detection thresholds based on C's review — **E1**
- [ ] Second false-positive filtering pass on heat detection specifically — **E1 + E2**
- [ ] Build/polish dashboard: distinguish PPE alerts vs. heat alerts visually, add trend view for heat readings — **E2**

### Testing
- [ ] Stress-test with varied images/conditions (lighting, crowding, simulated ambient temp swings) — **E1 + E2**

### Pitch & submission
- [ ] Draft "why this matters" narrative — injury/heat-illness cost data, why false-positive filtering matters for adoption — **C**
- [ ] Write README + submission writeup — **E2 leads, all contribute**
- [ ] Build demo script (live + backup recording) — **All**
- [ ] Rehearse pitch — **All**

---

## Suggested Repo Structure

```
/agents
  /ppe_detection/
  /heat_detection/
  /risk_scoring/
  /alert_routing/
  /logging/
/taxonomy/
  heat_scenarios.md       <- owned by C
  ppe_severity.md         <- owned by C
  heat_thresholds.md      <- owned by C
/data/
  sample_images/
  heat_proxy_or_synthetic/
/dashboard/
/specs/                   <- Architect-mode plan.md outputs, one per agent
AGENTS.md
REQUIREMENTS.md
TASKS.md
README.md
```

**Status note:** the structure above matches what's actually in the repo. `/taxonomy/` is clean (duplicate removed). `/specs/` currently has some duplicate plan files pending cleanup (see Week 2) alongside the real per-agent plan docs and the system design/contract references.