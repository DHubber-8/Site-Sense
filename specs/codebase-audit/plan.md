# Codebase Audit — Cleanup Plan

Status: audit complete, no code changed yet — this doc is the plan to review/assign before
implementation starts, per the spec-before-code workflow in `AGENTS.md`.

## Scope & method

Every module in `agents/`, `dashboard/`, `scripts/`, `tests/` was read line-by-line and
cross-checked against callers/callees, git history, and the pipeline contract in
`specs/system_design.md`. The full test suite was run and is green throughout (71 passed,
1 skipped — the checkpoint-dependent end-to-end test, expected without the trained model
present). No implementation changes were made during the audit itself.

## Findings

### P0 — Correctness bugs (silently broken data flow)

**1. Heat-compliance alerts never fire on real weather data** — `agents/heat_detection/agent.py:279-297`

`_passes_heat_proxy_safeguards()` requires `reading.metadata["elevated_duration_minutes"]` and
`["ambient_temperature_c"]` to be present, else it returns `False` immediately, and
`classify_heat_alert()` returns `None` before even checking temperature. Neither
`_parse_openweather_forecast()` nor `_parse_openmeteo_forecast()` ever sets those keys — they're
WBGT/sensor concepts, not forecast concepts. Net effect: **the entire Section-2
forecast-compliance path (FR2.1) is dead in production.** No matter how hot the forecast,
`HeatComplianceAlertAgent.assess()` with the real default client returns `alerts=[]`. This looks
like WBGT's sustained-elevation filter got copy-pasted into the forecast path, where a single
daily max-temp reading has no "duration" concept to begin with.

Every test fixture builds a `WeatherForecastReading` by hand and passes those metadata keys in
directly, so the test suite stays green while the feature is dead for a live run — the test
fixtures silently became the missing implementation instead of exercising the real one.

**2. `requires_review` is computed but never persisted** — `agents/logging/agent.py` (table
schema, INSERT, and `_record_from_row`) + `agents/risk_scoring/schema.py:30`

`RiskAssessment.requires_review` is set correctly by `risk_scoring` (e.g. low-confidence PPE
detections), but the SQLite table has no column for it, the INSERT never writes it, and
`_record_from_row()` reconstructs every record with the dataclass default (`False`). Every
record read back from storage — which is every record the live dashboard shows — has
`requires_review=False`, permanently. `dashboard/app.py` already has a comment at line 268
acknowledging this ("not persisted by the logging schema"), and the dead branches at line 270
and line 824 are effectively unreachable for real data. `dashboard/logic.py`'s
`active_review_count`/`review_items` are similarly always 0/empty against real records (though
see finding 4 — that module isn't even wired into the running app).

**3. Demo-data seeding bypasses the false-positive filter it's supposed to demonstrate** —
`scripts/seed_demo_data.py:142`

`_build_wbgt_assessments()` calls `classify_wbgt_risk(reading)` directly instead of going
through `WBGTRiskAgent`, which is where `_has_sustained_elevation()` lives.
`data/heat_proxy_or_synthetic/brief_spike.json` exists specifically to prove a transient spike
must *not* alert (asserted in `test_wbgt_risk_smoke.py` and `test_end_to_end_smoke.py` via
`WBGTRiskAgent`), but the seed script's shortcut means the demo database can show an alert the
real pipeline would suppress — a real risk if this is what gets shown to judges as "the
false-positive filter in action."

### P1 — Dead code & duplication (data-flow hygiene)

**4. `dashboard/logic.py` is orphaned.** It is imported **only** by
`tests/test_dashboard_smoke.py`. The running app (`dashboard/app.py`) never imports it and
recomputes equivalent metrics inline inside `render_dashboard()` (active-alert count, PPE
compliance %, heat-risk count, etc.) using different logic than `build_metrics()`/
`summarize_active_alerts()`. Two implementations of "summarize the records" exist, only one of
which runs, and the tested one is provably dead. Needs a real decision: wire `app.py` to use
`logic.py` (matches the module's evident intent), or delete `logic.py` and its tests as
superseded.

**5. Checkpoint-resolution logic duplicated verbatim.** `_resolve_ppe_checkpoint()` in
`scripts/seed_demo_data.py:62-76` and `_resolve_checkpoint()` in `scripts/build_reference_ppe.py`
implement identical "prefer configured `PPE_MODEL_PATH`, else newest
`runs/detect/*/weights/best.pt`" logic independently. A future checkpoint-layout change only
gets applied to whichever one someone remembers to edit.

**6. `PpeDetectionAgent._load_model()` caching is unreachable when `model_loader` is set** —
`agents/ppe_detection/agent.py:65-70`. The `model_loader()` branch returns before the
cache-check line runs, so every `detect()` call would reload from scratch. Currently latent —
nothing in the codebase passes `model_loader` — but it's a trap for whoever uses that
(evidently intentional) extension point next.

### P2 — Style / tooling (lower risk, still worth doing)

**7. No enforced formatter/linter.** `AGENTS.md` mandates `black .` after every edit, but
`pyproject.toml` has no `[tool.black]`/`[tool.ruff]` section and neither is a dev dependency —
the convention is documented but not enforced by anything runnable.

**8. Bare multi-exception `except` clauses (PEP 758, Python 3.14-only syntax)** at
`dashboard/app.py:224`, `:439`, `:707` — e.g. `except OSError, ValueError:`. This *is* valid
given `requires-python = ">=3.14"` (verified via `py_compile`), not a bug. But it's syntax from
a Python version that shipped in the current year, which most linters/IDEs/syntax highlighters
(and anyone still on 3.13) won't recognize yet. Worth parenthesizing
(`except (OSError, ValueError):`) purely for broad tooling compatibility and readability — zero
behavior change.

**9. `dashboard/app.py` is ~1090 lines**, one file mixing injected CSS, data access, and
rendering. Not urgent, but it's the natural next thing to get harder to navigate as the
dashboard grows further. Lower priority than P0/P1.

## Cleanup plan

| # | Item | Files touched | Verification |
|---|---|---|---|
| P0-1 | Fix heat-compliance safeguard: either drop the duration/ambient gate for the forecast path (it's a single daily max, not a sensor series — sustained-elevation doesn't apply the same way) or source those fields correctly | `agents/heat_detection/agent.py`, its README, `tests/test_heat_detection_smoke.py` | New test: real-shaped `WeatherForecastReading` (no synthetic metadata) above 35°C → alert fires |
| P0-2 | Add `requires_review` column to the SQLite schema + INSERT + `_record_from_row`; remove the now-dead dashboard comments/branches once real | `agents/logging/agent.py`, `dashboard/app.py` | Round-trip test: record → read back → `requires_review` preserved |
| P0-3 | Route `seed_demo_data.py`'s WBGT seeding through `WBGTRiskAgent` instead of calling `classify_wbgt_risk` directly | `scripts/seed_demo_data.py` | Re-seed, confirm `brief_spike` produces no alert in `data/site_sense.db` |
| P1-4 | Decide `dashboard/logic.py`'s fate: wire into `app.py`, or delete it + its tests | `dashboard/app.py` or `dashboard/logic.py` + `tests/test_dashboard_smoke.py` | Full suite green either way; dashboard manual smoke check |
| P1-5 | Extract shared `resolve_ppe_checkpoint()` (e.g. into `agents/ppe_detection/config.py`) | `scripts/seed_demo_data.py`, `scripts/build_reference_ppe.py`, `agents/ppe_detection/config.py` | Both scripts still resolve the same checkpoint |
| P1-6 | Fix or remove the `model_loader` caching branch | `agents/ppe_detection/agent.py` | New test exercising `model_loader` twice, asserting it's called once |
| P2-7 | Add `[tool.ruff]`/`black` config + dev dependency, run once repo-wide | `pyproject.toml` | `uv run ruff check .` / `uv run black --check .` clean |
| P2-8 | Parenthesize the three PEP 758 `except` clauses | `dashboard/app.py` | Full suite green (behavior-neutral) |
| P2-9 | (Optional, later) Split `dashboard/app.py` into styles/data/render modules | `dashboard/` | Full suite + manual dashboard check |

## Ownership note

P0 items are genuine functional bugs affecting judged behavior (heat alerts, review flags,
demo-data honesty) and should be signed off given `AGENTS.md`'s ownership split (E1 owns heat
detection; E2 owns risk-scoring/logging/dashboard). P1/P2 are safe to implement unilaterally.

Implementation, when approved, should proceed P0 → P1 → P2, one commit per numbered item, with
a test written or fixed before each change per the project's TDD/hostile-reviewer testing
standard.
