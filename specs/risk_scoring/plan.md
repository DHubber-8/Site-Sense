# Risk Scoring Agent Plan

## Goal
Normalize PPE and heat detection output into a single, unified `RiskAssessment`
schema, per `specs/system_design.md`, so downstream agents don't need to know
about three different source-specific severity naming schemes.

## Scope
- Consume `PpeDetectionBatch`, `HeatComplianceAlertBatch`, and `WBGTRiskBatch`.
- Map each source's severity into the shared `Severity` enum (NONE/MINOR/MODERATE/CRITICAL).
- Attach recommended actions from the taxonomy files (`regulatory_actions`/`ai_actions`
  already present on heat alerts; PPE actions need to be pulled from
  `taxonomy/ppe_severity.md`'s "Recommended Action" sections per tier).
- Preserve the original detection/alert in `source_detail` for traceability —
  never discard the raw data, only add structure on top of it.
- Leave alert dispatch and persistence to `alert_routing` and `logging` — this
  agent only classifies and normalizes.

## Implementation Steps
1. Define `Severity` enum and `RiskAssessment` schema (per system_design.md §5).
2. Implement PPE scoring: read `taxonomy/ppe_severity.md`, build a lookup from
   PPE class label → severity tier. **Confirm the label set matches exactly**
   what `agents/ppe_detection` actually outputs (helmet/no_helmet/etc.) —
   don't hand-guess labels, pull them from a real detection run.
3. Implement heat compliance scoring: direct Level 1/2/3 → MINOR/MODERATE/CRITICAL
   mapping (no judgment call needed here, see system_design.md §3).
4. Implement WBGT scoring: apply the Normal/Caution/High Risk/Extreme →
   NONE/MINOR/MODERATE/CRITICAL mapping — **do not implement this step until
   C has confirmed the mapping in system_design.md §3.**
5. Write the zone field as `None` for now if the open question in
   system_design.md §6 hasn't been resolved yet — don't block this agent's
   progress on that decision, just don't fabricate zone data either.
6. Add a smoke test per source type, plus one test confirming `source_detail`
   round-trips the original detection without data loss.

## Files
- `agents/risk_scoring/__init__.py`
- `agents/risk_scoring/schema.py`
- `agents/risk_scoring/agent.py`
- `agents/risk_scoring/README.md`
- `tests/test_risk_scoring_smoke.py`

## Risks
- The WBGT 4→3 tier mapping is a domain decision, not yet confirmed by C —
  implementing it before sign-off risks rework if C's judgment differs from
  the proposed mapping.
- PPE label-to-severity lookup will silently produce wrong results if the
  taxonomy's example labels don't exactly match the model's real output
  labels — verify against real detection output, not the taxonomy doc alone.
- No `zone` field exists upstream yet — this agent should not invent one,
  only pass through `None` until the schema gap is resolved at the source.
