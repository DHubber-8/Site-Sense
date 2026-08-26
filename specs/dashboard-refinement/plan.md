# Dashboard refinement plan

## Goal
Refine the Site Sense dashboard presentation so it reads calm and operational for field
managers, surface real PPE pipeline output alongside heat stress in the demo, and replace the
raw JSON/code dump in incident details with readable labelled fields.

## Constraints and data boundary
- Presentation only in `dashboard/app.py`: no changes to alert logic, record filtering, or
  metric calculations.
- Do not modify `/agents/**`, `/taxonomy/**`, scoring, routing, or taxonomy logic.
- No fabricated or placeholder alert data. PPE records must come from the real detection →
  scoring → routing → logging pipeline.
- Keep the existing Streamlit + injected-CSS pattern; no framework rewrite.

## Findings
1. **PPE is absent from the demo database.** `data/site_sense.db` holds 72 records, all
   `heat_wbgt` / `heat_compliance`. `scripts/seed_demo_data.py` calls `PpeDetectionAgent()`
   with the default `PPE_MODEL_PATH` (`runs/detect/train/weights/best.pt`), whose `weights/`
   directory is empty; the resulting `FileNotFoundError` is swallowed by a bare
   `except Exception: continue`, so every PPE image is skipped silently. Trained weights do
   exist at `runs/detect/train-10/weights/best.pt`. Running the pipeline against them yields
   18 routed PPE alerts across `ppe` and `ppe_coverage`.
2. **Incident details expose internal codes.** `_incident_details` renders
   `st.code(json.dumps({"bounding_box": ..., "model_metadata": detail}))`, leaking
   `class_id`, `raw_label`, `positive_label`, `negative_label`, and simulation internals.
3. **Incident labels are ambiguous.** `_incident_name` renders a low-confidence `ppe` review
   item and a `ppe_coverage` gap identically to a confirmed item (both "Gloves").
4. **"View details" is a dead control.** It writes `st.session_state["selected_incident"]`,
   which nothing reads.
5. **Heat chart copy overstates the data.** It is labelled "Average worker temperature" while
   plotting the WBGT/ambient proxy series, contrary to the AGENTS.md heat-proxy rule.
6. Styling: saturated status badges, unstyled disabled buttons, no metric-delta suppression,
   thin section separation, flat typographic hierarchy between title/section/label/metadata.

## Implementation
- `scripts/seed_demo_data.py`: resolve the newest available `runs/detect/*/weights/best.pt`
  when the configured checkpoint is missing, pass it via the agent's existing `model_path`
  field, and report skipped images instead of swallowing the error. Seeding logic itself is
  unchanged.
- `dashboard/app.py`:
  - CSS: desaturate severity and status badges while keeping red/amber/blue semantics; hide
    Streamlit metric deltas; strengthen label/value/metadata type hierarchy; add section
    spacing, softer empty states, and muted disabled-button styling; add a `detail-grid`
    layout for labelled incident fields.
  - `_incident_name`: distinguish confirmed violations, low-confidence reviews, coverage gaps,
    and heat alert levels.
  - `_incident_details`: labelled field grid per source plus recommended actions; drop the
    JSON block and internal identifiers; keep the record reference as muted metadata so the
    incident-ID search keeps working; show the confidence bar only when confidence exists.
  - `_alert_card`: replace the dead "View details" button with an inline details expander.
  - Heat chart copy: name the plotted series honestly as a proxy reading.

## Validation
- `uv run pytest tests/test_dashboard_smoke.py`
- Full suite for regressions, plus a `dashboard.app` import check.
- Re-seed and confirm PPE and heat records both appear in the demo database.

## Follow-up round — alert mix, sidebar, reference imagery

### Findings
7. The separate "PPE observations" panel split attention: PPE counts sat beside the heat chart
   while the alert list showed only heat, because 72 heat records buried the 2 missing-PPE
   violations below the 10-row cut.
8. Streamlit only reveals the sidebar collapse control on hover, so on a wall-mounted or
   touch display the sidebar reads as fixed with no way to reclaim the space.
9. Incident evidence imagery is not possible from stored records: `assess_ppe` builds
   `source_detail` from `PpeDetection.to_dict()` (item, confidence, bounding box, class id,
   raw label) and drops `PpeDetectionBatch.source_image`, so no persisted record references
   the frame it came from.

### Implementation
- Drop `_render_ppe_breakdown`. Add `_visible_alerts()`: the overview surfaces missing-PPE
  violations (`ppe` source, `no_*` label) and heat alerts, ranked most-severe-then-most-recent,
  with `PPE_ALERT_SLOTS` reserved so a long run of heat readings cannot bury a PPE violation.
  Positive detections and unverified-coverage flags remain in the incident log. Metric
  calculations are untouched.
- CSS: force `stSidebarCollapseButton` / `stExpandSidebarButton` permanently visible with a
  bordered surface treatment so collapse and re-show are always discoverable.
- Reference imagery: `data/reference_ppe/<item>.{jpg,jpeg,png,webp}`, resolved via
  `_ppe_item_key()` so `no_goggle` and `goggles` share one file. Rendered in PPE incident
  details and beside guideline steps, captioned as reference images — never as evidence.
  A missing file renders nothing rather than a placeholder.

### Flagged for a human (not changed)
- Persisting `PpeDetectionBatch.source_image` through risk scoring and logging is the only way
  to show true incident evidence. That is an `/agents/` schema change — E1/E2's call.

## Third round — reference imagery from the real pipeline

### Decision
Correct-PPE imagery is produced by the agents from the sample image data, not hand-made
placeholders. Heat gets no imagery by design: heat detection runs on proxy/synthetic condition
data rather than frames, so there is nothing for it to illustrate.

### Implementation
- New `scripts/build_reference_ppe.py`: runs `PpeDetectionAgent` over `data/sample_images/`,
  uses `RiskScoringAgent` to decide which detections are compliant (`Severity.NONE`, not
  flagged for review), crops the best compliant example per item into `data/reference_ppe/`,
  and writes `manifest.json` with source frame, confidence, and crop box.
- Selection ranks by bounding-box area, not confidence: confidence measures model certainty,
  not crop legibility. `PREFERRED_SOURCES` pins `vest` and `gloves` to human-reviewed frames,
  choosing only among detections the scoring agent already accepted as compliant.
- Crops are square, padded `CROP_PADDING` around the box, floored at `MIN_CROP_PX`, and clamped
  to the source frame so nothing is upscaled.
- Dashboard: reference images now also appear in the PPE response checklist (the
  acknowledge/resolve dialog), above the steps. `_reference_manifest()` supplies the detection
  confidence shown in each caption.

### Review notes
- Automatic selection alone was not sufficient. Highest-confidence gave a 91%-confidence
  "helmet" crop with no head in frame; largest-box gave a mirrored press screenshot for vest.
  Both criteria are recorded in the script comments so the reasoning is not lost.
- `data/reference_ppe/no_helmet.jpg` predates this work and is unused: `_ppe_item_key()` maps
  `no_helmet` to `helmet`, so lookups resolve to `helmet.jpg`. Flagged for deletion.
