# System Design — Risk Scoring, Alert Routing, Logging

Owner: E1 (taking over from E2)
Status: draft — the unified severity mapping below needs C's sign-off before implementation starts, since it makes a domain judgment call not stated in the taxonomy files.

## 1. Why this doc exists

`specs/detection_output_contract.md` was marked complete in `TASKS.md` but does not
exist in the repo — this document replaces it and covers the same ground (real
schema shapes from the two detection agents), plus the design for the three
remaining agents.

## 2. The core problem: three severity schemes that don't line up

| Source | Scheme | Direction |
|---|---|---|
| PPE (`taxonomy/ppe_severity.md`) | Critical(3) / Moderate(2) / Minor(1) | 3-tier, numeric |
| Heat compliance (`heat_thresholds.md` §2) | Level 1 / Level 2 / Level 3 | 3-tier, Level 3 = worst |
| Heat WBGT (`heat_thresholds.md` §1) | Normal / Caution / High Risk / Extreme | **4-tier**, no numeric mapping given |

Alert routing and logging should not need to know about three different naming
schemes. Risk scoring's real job is **normalizing all three into one shared
output**, not just relabeling detections.

## 3. Proposed unified severity model — needs C's sign-off

```python
class Severity(Enum):
    NONE = 0      # no alert — e.g. WBGT "Normal", or no PPE violation detected
    MINOR = 1
    MODERATE = 2
    CRITICAL = 3
```

**Direct mappings (no judgment call needed):**
- PPE: Critical→CRITICAL, Moderate→MODERATE, Minor→MINOR
- Heat compliance: Level 3→CRITICAL, Level 2→MODERATE, Level 1→MINOR

**The judgment call — WBGT's 4 tiers into 3:**
```
Normal    → NONE       (no alert, matches existing agent behavior)
Caution   → MINOR
High Risk → MODERATE
Extreme   → CRITICAL
```
This collapses WBGT's "High Risk" and "Extreme" distinction down to MODERATE/CRITICAL.
**This is a real domain decision, not an engineering one** — it decides how urgently
"reduce workload, monitor closely" (High Risk) gets treated versus "suspend outdoor
work" (Extreme). Flag this mapping to C before building risk-scoring against it;
don't treat it as settled just because it's written here.

## 4. Data flow

```
PpeDetectionBatch ──┐
                     ├──> risk_scoring.assess() ──> list[RiskAssessment]
HeatComplianceAlertBatch ──┤                              │
                     │                                    ▼
WBGTRiskBatch ───────┘                          alert_routing.route()
                                                            │
                                                            ▼
                                                  logging.record()
```

Each detection batch is assessed independently — risk-scoring doesn't need to wait
for all three sources; it processes whatever batch it's given and emits zero or
more `RiskAssessment` records.

## 5. Proposed shared schema

```python
@dataclass(frozen=True, slots=True)
class RiskAssessment:
    source: str              # "ppe" | "heat_compliance" | "heat_wbgt"
    severity: Severity
    label: str                # e.g. "no_helmet", "Level 2", "High Risk"
    description: str          # human-readable, for alert/log display
    zone: str | None          # see open question below
    recommended_actions: list[str]   # from taxonomy's regulatory_actions/ai_actions
    source_detail: dict[str, Any]    # the original detection/alert, kept for traceability
    assessed_at: datetime
```

## 6. Open question — no `zone` field exists anywhere yet

Neither `PpeDetectionBatch` nor the heat batches carry a `zone`/location field
today, but the dashboard mockup and C's scenario docs both assume per-zone
tracking. **This needs to be resolved before or during risk-scoring build** —
either detection agents get a zone field added upstream (small schema change),
or risk-scoring defaults to a single-site model for now and zone support is a
documented gap, not silently assumed.

## 7. Agent responsibilities (kept separate, not one mega-agent)

- **`risk_scoring`** — normalizes detections into `RiskAssessment` per §3–5. Reads
  taxonomy files for actions/thresholds. Does not decide *what happens next*.
- **`alert_routing`** — takes `RiskAssessment`, decides log-only vs. active
  notification based on `Severity`. Does not persist anything itself.
- **`logging`** — persists every `RiskAssessment` + routing decision, timestamped.
  Single source of truth for the dashboard and for audit/compliance history.

Kept as three separate agents (not merged) so each can be tested independently,
matching the existing pattern from `ppe_detection`/`heat_detection`.
