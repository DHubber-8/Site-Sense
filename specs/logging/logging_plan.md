# Logging Agent Plan

## Goal
Persist every `RiskAssessment` and its `RoutedAlert` routing decision as a
timestamped, queryable record — the single source of truth for both the
eventual dashboard and any compliance/audit trail.

## Scope
- Store every risk assessment + routing decision that passes through the
  pipeline, not just ones that triggered a notification — a MINOR/log-only
  entry still needs a record for historical/compliance purposes.
- Support basic querying: by date range, by severity, by source
  (ppe/heat_compliance/heat_wbgt) — this is what the dashboard will need to
  filter against later.
- A simple file-based store (JSON lines or SQLite) is enough for a hackathon
  build — no need for a real database.

## Implementation Steps
1. Define the storage schema — essentially `RoutedAlert` plus a generated
   record ID.
2. Implement a simple append-only write path (`record()`).
3. Implement basic read/query methods needed by the dashboard: recent
   records, filter by severity, filter by date range.
4. Decide storage backend: SQLite is preferable over raw JSON lines if any
   filtering/querying beyond "read everything and filter in Python" is
   needed — cheap to set up, avoids reinventing query logic.
5. Add a smoke test: write a few records, confirm they're retrievable and
   correctly filtered.

## Files
- `agents/logging/__init__.py`
- `agents/logging/schema.py`
- `agents/logging/agent.py` (or `store.py` if "agent" doesn't fit — this is
  closer to a data-access layer than a decision-making agent)
- `agents/logging/README.md`
- `tests/test_logging_smoke.py`

## Risks
- Don't over-build this — a hackathon demo needs "records persist and can be
  filtered for the dashboard," not a production-grade logging system. Keep
  scope tight given the remaining timeline.
- If SQLite is chosen, make sure the database file itself doesn't get
  committed to git — treat it like `runs/`, add to `.gitignore`.
