# Tasks — Safety Monitoring & Response Agent (3 weeks, 3-person team)

Team: **E1, E2** (CS) · **C** (Civil Engineering)
Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Week 1 — Foundations & Scoping

### Repo & tooling
- [ ] Init repo, add `AGENTS.md` with project conventions (agent folder structure, data schema rules, commit format) — **E2**
- [ ] Run an Architect-mode (Zoo Code) session per agent to generate `/specs/*.md` plan docs before any code — **E1 + E2**
- [ ] Set up base folder structure (see repo layout below) — **E2**

### Research & taxonomy (C)
- [ ] Research PPE safety codes → draft severity taxonomy (minor/moderate/critical) — **C**
- [ ] Research heat-stress/heat-exhaustion occupational guidance → draft heat-severity thresholds — **C**
- [ ] Decide + document the heat-detection data approach (real thermal proxy dataset vs. simulated model) — **C + E1**

### PPE pipeline (E1)
- [ ] Evaluate pretrained PPE-detection models, select one — **E1**
- [ ] Get detection running standalone on sample images (no pipeline integration yet) — **E1**

### Heat pipeline (E1 + E2)
- [ ] Source or simulate a starter thermal/heat dataset — **E2**
- [ ] Prototype the heat-reading extraction method (from thermal proxy or RGB+ambient model) — **E1**

### End of Week 1 checkpoint
- [ ] Team sync: confirm both detection approaches are technically viable before committing further — **All**

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
