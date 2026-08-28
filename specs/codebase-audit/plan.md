# Codebase Audit — Cleanup Plan

Status: two review rounds complete. **Round 1 (P0-P2-9)** and **Round 2 (D1-D4, a deeper
concurrency/security/integrity-focused pass)** both implemented and verified — test-first where
behavior changed, full suite green throughout, re-seeded demo data confirmed the real-world P0
fixes, live dashboard boot confirmed the P2-9 module split, and a real race condition (D1) was
reproduced before and after its fix. Round 2 also caught and corrected a Round-1 status that had
silently regressed (P2-8). See "Round 2" below.

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
| P0-1 ✅ | Dropped the duration/ambient gate from `classify_heat_alert()` — it never matched `taxonomy/heat_thresholds.md` Section 2 (forecast-max-temperature only, no duration/ambient concept) and no real weather client ever populated the metadata it required | `agents/heat_detection/agent.py`, `scripts/seed_demo_data.py`, `dashboard/app.py`, `tests/test_heat_detection_smoke.py` | New test `test_classify_heat_alert_fires_for_real_shaped_forecast_reading` (RED confirmed, now GREEN); removed the now-lying `test_classify_heat_alert_requires_proxy_safeguards`; full suite green; **re-seeded demo data and confirmed a real live alert now records** (`heat_compliance: {'MODERATE': 2}`, previously always empty) |
| P0-2 ✅ | Added `requires_review` column to the SQLite schema, INSERT, and `_record_from_row`, plus an `ALTER TABLE` migration for pre-existing databases; removed the now-stale dashboard comment | `agents/logging/agent.py`, `dashboard/app.py`, `tests/test_logging_smoke.py` | New test `test_record_persists_requires_review_flag` (RED confirmed, now GREEN); migration verified against the real pre-existing `data/site_sense.db` (column added, existing rows default to `False`) |
| P0-3 ✅ | Routed `seed_demo_data.py`'s WBGT seeding through `WBGTRiskAgent` (via a small replay reading-source) instead of calling `classify_wbgt_risk` directly | `scripts/seed_demo_data.py`, `tests/test_seed_demo_data_smoke.py` (new) | New test `test_brief_spike_scenario_produces_no_wbgt_alert` (RED confirmed, now GREEN); re-seeded and confirmed the `brief_spike` transient reading (`wbgt_c=29.81`) produces no alert in `data/site_sense.db` |
| P1-4 ✅ | Deleted `dashboard/logic.py` and its dedicated tests. Confirmed it was not a simple wire-in: its output shape (`active_review_count`, `by_severity`, `by_source`) doesn't match any metric `render_dashboard()` actually displays (`Active alerts`, `PPE compliance %`, `Heat risk exposure`, `Incidents today`, all computed inline) — reviving it would mean designing new UI surfaces, which is feature work, not cleanup | `dashboard/logic.py` (removed), `tests/test_dashboard_smoke.py` | Full suite green; only the one non-`logic.py` test in that class (`test_render_metric_card_...`) kept |
| P1-5 ✅ | Extracted `resolve_trained_checkpoint()` into `agents/ppe_detection/config.py`; both scripts now call it instead of maintaining identical local copies | `agents/ppe_detection/config.py`, `scripts/seed_demo_data.py`, `scripts/build_reference_ppe.py`, `tests/test_ppe_detection_smoke.py` | New `ResolveTrainedCheckpointSmokeTest` (3 cases: prefers configured, falls back to newest run, returns `None`); confirmed against the real repo it still resolves `runs/detect/train-10/weights/best.pt` |
| P1-6 ✅ | Reordered `_load_model()`'s cache check ahead of the `model_loader` branch so a loaded model is actually reused | `agents/ppe_detection/agent.py` | New test `test_model_loader_is_only_invoked_once_across_detect_calls` (RED confirmed: 2 calls before the fix; GREEN after) |
| P2-7 ✅ | Added `black` as a dev dependency and a minimal `[tool.black]` config (`target-version = ["py314"]`), matching the `requires-python` floor. Ran it repo-wide | `pyproject.toml`, `uv.lock`, 14 files reformatted (whitespace/line-wrapping only) | `uv run black --check .` → `32 files would be left unchanged`; full suite green before and after |
| P2-8 ❌→ reverted | **Correction:** originally marked done (parenthesized the three PEP 758 `except` clauses), but this was never actually stable — `black`, once it targets `py314+` (forced by `requires-python = ">=3.14"`, with or without an explicit `[tool.black] target-version`), rewrites `except (A, B):` back to `except A, B:` as its canonical form for that target. Every subsequent `black .` run (required by `AGENTS.md`, enforced by P2-7) silently undid the fix — confirmed by isolating it in a throwaway probe file. P2-7 and P2-8 were fighting each other; P2-7 (matching the formatter to the project's real `requires-python`) is the correct one to keep, so P2-8 is abandoned and the bare-comma form is accepted as canonical | `dashboard/app.py` | `black .` twice in a row now reports `34 files left unchanged` both times — confirmed stable/idempotent; full suite green |
| P2-9 ✅ | Split `dashboard/app.py` (1074 lines) into `dashboard/styles.py` (`inject_css()`, ~110 lines of pure CSS, zero logic) and `dashboard/data.py` (the LoggingAgent I/O boundary: `DATABASE_PATH`, `SOURCE_LABELS`, `STATUS_LABELS`, `_agent`, `_assessment`, `_query_records`, `_today_records`, ~90 lines). `app.py` (now 904 lines) keeps every function the test suite touches by name (`_detail_rows`, `_incident_name`, `_visible_alerts`, etc.) plus all page rendering — checked first that none of the moved functions were referenced as `app.X` in tests, so zero test-file changes were needed | `dashboard/styles.py` (new), `dashboard/data.py` (new), `dashboard/app.py` | Full suite green before and after; `black --check .` clean; actually launched `streamlit run dashboard/app.py` headlessly — HTTP 200, clean server log, no traceback |

## Ownership note

P0 items are genuine functional bugs affecting judged behavior (heat alerts, review flags,
demo-data honesty) and should be signed off given `AGENTS.md`'s ownership split (E1 owns heat
detection; E2 owns risk-scoring/logging/dashboard). P1/P2 are safe to implement unilaterally.

Implementation, when approved, should proceed P0 → P1 → P2, one commit per numbered item, with
a test written or fixed before each change per the project's TDD/hostile-reviewer testing
standard.

## Round 2 — deep-dive review (post P0-P2)

A second, deeper pass over the whole codebase after P0-P2 landed, specifically hunting for
what a correctness/reuse-focused first pass wouldn't naturally surface: concurrency, security,
resource handling, and documentation-integrity issues.

**D1 ✅ — `LoggingAgent` schema migration had a check-then-act race.** `_migrate_requires_review_column`
read `PRAGMA table_info` then conditionally ran `ALTER TABLE` with no locking. Reproduced directly:
8 threads constructing `LoggingAgent` against the same pre-migration database crashed 7 of 8 with
`sqlite3.OperationalError: duplicate column name`. `dashboard/data.py`'s `_agent()` (called
3-4 times per Streamlit rerun before D2, below) made this the normal case, not an edge case, for
any concurrent dashboard session hitting an unmigrated `data/site_sense.db`. Fixed by catching the
"duplicate column" `OperationalError` as a no-op — the losing thread's schema is already correct,
it just didn't win the race to add it. New test
`test_concurrent_instantiation_against_a_pre_migration_database_does_not_crash` (RED confirmed: 7/8
threads raised; GREEN after). Files: `agents/logging/agent.py`, `tests/test_logging_smoke.py`.

**D2 ✅ — `dashboard/data.py`'s `_agent()` reconnected on every call.** Original first-pass finding
that never got a P-number in the table above (a gap in the initial triage). Every Streamlit rerun
(every filter change, every incident expand) opened 3-4 fresh sqlite connections and re-ran
`CREATE TABLE IF NOT EXISTS` + the migration check purely to read the same data. Fixed with
`@st.cache_resource` on `_agent()` — one `LoggingAgent` per process; each query still opens its own
short-lived connection, only the one-time setup work is now actually one-time. This also shrinks
the race window in D1 to process-startup only. File: `dashboard/data.py`.

**D3 ✅ — dead `_agent` import in `dashboard/app.py`.** Left over from the P2-9 split: `app.py`
imported `_agent` from `dashboard.data` but never called it (the functions that need it,
`_query_records`/`_today_records`, live in `data.py` itself). Removed.

**D4 — P2-8 correction.** See the corrected P2-8 row above — not a new defect, a discovery that the
original "done" claim didn't hold, caught by re-grepping for the specific fix instead of trusting a
general `black --check .` pass.

Verification for all of D1-D3: full suite green (76 passed, up from 75 — the one new race test),
`black --check .` clean, `python -m py_compile` clean on every touched file.
