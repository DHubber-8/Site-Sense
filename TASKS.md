# Tasks — Safety Monitoring & Response Agent (3 weeks, 3-person team)

Team: **E1, E2** (CS) · **C** (Civil Engineering)
Legend: `[ ]` not started · `[~]` in progress · `[x]` done

## Week 1 — Foundations & Scoping

### Repo & tooling
- [x] Init repo, add `AGENTS.md` with project conventions (agent folder structure, data schema rules, commit format) — **E2**
- [x] Set up base folder structure (see repo layout below) — **E2**
- [x] Add Copilot-specific config (`.github/agents/`, `.github/instructions/`, `.github/prompts/`) mirroring `AGENTS.md` conventions — **E2**
- [x] Run an Architect-mode session for the PPE detection agent, producing `/specs/ppe_detection/plan.md` — **E1**
- [ ] Run an Architect-mode session for the heat detection agent, producing `/specs/heat_detection/plan.md` — **E1** (blocked, see below)

### Research & taxonomy (C)
- [x] Research PPE safety codes → draft severity taxonomy (minor/moderate/critical) — **C** (merged)
- [x] Research heat-stress/heat-exhaustion occupational guidance → draft heat-severity thresholds — **C** (merged)
- [ ] Decide + document the heat-detection data approach — **C + E1** — **blocking task, see note below**

### PPE pipeline (E1)
- [x] Evaluate pretrained PPE-detection models, select one — **E1** (YOLO26, base checkpoint; fine-tuning on Construction-PPE dataset in progress)
- [x] Get detection running standalone on sample images — **E1** (fixture-based smoke test passing)

### Heat pipeline (E1 + E2)
- [ ] Source or build a starter thermal/heat data source — **E2** (under discussion: public thermal dataset vs. simulated model vs. DIY ESP32 + AMG8833 sensor)
- [ ] Prototype the heat-reading extraction method — **E1** (blocked on the above)

### End of Week 1 checkpoint
- [ ] Team sync: confirm both detection approaches are technically viable before committing further — **All**

> **Open blocker carried into Week 2 risk:** the heat-detection data approach still isn't decided. This is now the single item most likely to compress Week 2 if it slips further — prioritize this conversation before anything else on the heat side.

---

## Week 2 — Core Build

### PPE + heat integration
- [ ] Wire PPE detection agent into pipeline (image → detections) — **E1**
- [ ] Wire heat detection agent into pipeline (image/data → temperature reading) — **E1**
- [ ] Build false-positive filtering pass for heat readings (duration tracking, ambient-temp compensation, baseline calibration) — **E1 + E2**

### Risk scoring & alerts
- [ ] Build risk-scoring agent using C's PPE taxonomy — **E2**
- [ ] Build risk-scoring agent using C's heat thresholds — **E2**
- [ ] Build alert-routing agent (severity-based: log-only vs. active notification) — **E2**
- [ ] Build compliance/incident logging store — **E2**

### Validation
- [ ] Run first end-to-end test (image/data in → detections → scoring → alert → log) — **E1 + E2**
- [ ] Review false positives/negatives from test run (both PPE and heat), adjust rules — **C**

### End of Week 2 checkpoint
- [ ] Full pipeline runs end-to-end for both detection types — **All**

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

**Week 1 start:** only `AGENTS.md`, `/specs/`, and stub folders should exist by day 2 — get the plan docs written before code. `/taxonomy/` files should be drafted (even roughly) by day 3-4 so the scoring agents in Week 2 aren't blocked waiting on C.