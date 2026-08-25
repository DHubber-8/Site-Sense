# Dashboard rebuild plan

## Goal
Replace the previous filter dump with a light, responsive Site Sense operations dashboard that supports three navigable pages: Dashboard, Incident log, and Guidelines.

## Constraints and data boundary
- Edit only `dashboard/app.py` and this plan.
- Keep the rebuild display-only; do not modify logging, scoring, routing, or taxonomy agents.
- Read records through `LoggingAgent.recent()`, `filter_by_severity()`, `filter_by_source()`, and `filter_by_date_range()` only.
- Do not seed records or render placeholder/demo alert descriptions. Empty states must be honest.
- Because the existing logging schema has no status, acknowledgement, resolution, or guideline tables, keep workflow status and customized guidelines in Streamlit session state for this display-only build. Make the limitation explicit in code structure and never present session state as durable persistence.

## Implementation
- Inject a complete light theme CSS layer and use a responsive sidebar/mobile header shell.
- Load filtered records by composing the existing query methods, then classify categories from source values.
- Derive metrics from real records, including a date-range query for the current-day incident count.
- Render heat telemetry as an amber chart with an explicit 38 C threshold series.
- Use `st.dialog` for acknowledgement/resolution, with guideline checklist, notes, and non-blocking submission.
- Build incident rows with technical details, confidence, telemetry, bounding box, model metadata, and response-time formatting.
- Implement built-in China safety response protocols and compact inline guideline editing with `st.data_editor`/session state. Reordering is a stretch goal and will not be implied if unsupported.

## Validation
- Run the dashboard smoke tests and a Python compile/import check.
- Confirm no placeholder seed text remains and the dashboard module imports from outside the repository root.
