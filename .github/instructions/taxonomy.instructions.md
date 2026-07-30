---
applyTo: "taxonomy/**"
---

# Taxonomy files — read-only for AI

Files in this folder (`ppe_severity.md`, `heat_thresholds.md`) encode real safety-code
research and occupational heat-stress thresholds, owned by the civil engineering
teammate (C).

- You may **read** these files freely for context when building detection, scoring,
  or alert-routing agents.
- You must **not edit these files directly**, even if asked to "just fix a typo" or
  "update the threshold." If a change seems necessary, stop and explain what should
  change and why — let a human (ideally C) make the edit.
- Do not infer or invent severity thresholds that aren't already written here. If a
  value is missing, flag it as missing rather than filling in a plausible-sounding
  number.