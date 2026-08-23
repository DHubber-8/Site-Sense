# Alert Routing Agent Plan

## Goal
Take a `RiskAssessment` (from `risk_scoring`) and decide what happens next:
silent log entry, or an active notification.

## Scope
- Input: one or more `RiskAssessment` records.
- Decision, based on `Severity`:
  - `NONE` — no action, nothing to route.
  - `MINOR` — log only, no active notification.
  - `MODERATE` — notify site supervisor, non-urgent.
  - `CRITICAL` — immediate/urgent notification.
- Output: a `RoutedAlert` record capturing the routing decision made and when,
  so `logging` has a full record of not just what was detected but what the
  system did about it.
- Actual notification delivery (push notification, SMS, dashboard push) is
  **out of scope for this pass** — routing decides *what* should happen;
  wiring to a real notification channel can be a later, separate task once
  the dashboard exists to receive it.

## Implementation Steps
1. Define `RoutedAlert` schema: the original `RiskAssessment`, the routing
   decision (`log_only` | `notify` | `notify_urgent`), and a timestamp.
2. Implement the routing function as a straightforward severity → decision
   mapping — keep this simple, per the original task note ("a working
   if-severity-is-X-do-Y is enough for now").
3. Make the routing thresholds configurable (e.g. which severity triggers
   `notify_urgent`) rather than hardcoded, in case this needs tuning later
   without a code change.
4. Add a smoke test covering all four severity levels, confirming each maps
   to the correct routing decision.

## Files
- `agents/alert_routing/__init__.py`
- `agents/alert_routing/schema.py`
- `agents/alert_routing/agent.py`
- `agents/alert_routing/README.md`
- `tests/test_alert_routing_smoke.py`

## Risks
- Keep this agent genuinely simple — the temptation is to build real
  notification delivery here, but that's a separate concern from deciding
  *whether* something warrants urgency. Resist scope creep here given the
  remaining timeline.
