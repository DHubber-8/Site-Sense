from __future__ import annotations

from datetime import datetime, timezone

from agents.heat_detection.schema import HeatComplianceAlertBatch, WBGTRiskBatch
from agents.ppe_detection.schema import PpeDetectionBatch

from .schema import RiskAssessment, Severity

PPE_SEVERITY_BY_LABEL: dict[str, Severity] = {
    "none": Severity.CRITICAL,
    "no_helmet": Severity.CRITICAL,
    "no_boots": Severity.CRITICAL,
    "no_gloves": Severity.MODERATE,
    "no_goggle": Severity.MODERATE,
    "chin_strap_unfastened": Severity.MINOR,
    "vest_partially_covered": Severity.MINOR,
    "damaged_ppe": Severity.MINOR,
}

PPE_RECOMMENDED_ACTIONS: dict[Severity, list[str]] = {
    Severity.CRITICAL: [
        "Stop work immediately",
        "Notify site supervisor",
        "Correct PPE before continuing work",
    ],
    Severity.MODERATE: [
        "Correct before continuing work",
        "Supervisor notification",
    ],
    Severity.MINOR: [
        "Worker reminder",
        "Replace PPE if needed",
    ],
}

HEAT_COMPLIANCE_SEVERITY_BY_LEVEL: dict[str, Severity] = {
    "Level 1": Severity.MINOR,
    "Level 2": Severity.MODERATE,
    "Level 3": Severity.CRITICAL,
}

WBGT_SEVERITY_BY_LEVEL: dict[str, Severity] = {
    "Normal": Severity.NONE,
    "Caution": Severity.MINOR,
    "High Risk": Severity.MODERATE,
    "Extreme": Severity.CRITICAL,
}


def _description(label: str, severity: Severity) -> str:
    if label == "none":
        return "No PPE detected"
    return f"PPE violation detected: {label} ({severity.name.lower()} severity)"


def assess_ppe(batch: PpeDetectionBatch) -> list[RiskAssessment]:
    """Convert PPE violation detections into normalized risk assessments."""

    assessed_at = datetime.now(timezone.utc)
    assessments: list[RiskAssessment] = []
    for detection in batch.detections:
        severity = PPE_SEVERITY_BY_LABEL.get(detection.item)
        if severity is None:
            continue

        assessments.append(
            RiskAssessment(
                source="ppe",
                severity=severity,
                label=detection.item,
                description=_description(detection.item, severity),
                zone=None,
                recommended_actions=list(PPE_RECOMMENDED_ACTIONS[severity]),
                source_detail=detection.to_dict(),
                assessed_at=assessed_at,
            )
        )

    return assessments


def assess_heat_compliance(batch: HeatComplianceAlertBatch) -> list[RiskAssessment]:
    """Convert heat compliance alerts into normalized risk assessments."""

    assessed_at = datetime.now(timezone.utc)
    assessments: list[RiskAssessment] = []
    for alert in batch.alerts:
        try:
            severity = HEAT_COMPLIANCE_SEVERITY_BY_LEVEL[alert.level]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported heat compliance level: {alert.level}"
            ) from exc

        assessments.append(
            RiskAssessment(
                source="heat_compliance",
                severity=severity,
                label=alert.level,
                description=alert.title,
                zone=None,
                recommended_actions=[
                    *alert.regulatory_actions,
                    *alert.ai_actions,
                ],
                source_detail=alert.to_dict(),
                assessed_at=assessed_at,
            )
        )

    return assessments


def assess_wbgt(batch: WBGTRiskBatch) -> list[RiskAssessment]:
    """Convert WBGT risk alerts into normalized risk assessments."""

    assessed_at = datetime.now(timezone.utc)
    assessments: list[RiskAssessment] = []
    for alert in batch.alerts:
        try:
            severity = WBGT_SEVERITY_BY_LEVEL[alert.level]
        except KeyError as exc:
            raise ValueError(f"Unsupported WBGT level: {alert.level}") from exc

        assessments.append(
            RiskAssessment(
                source="heat_wbgt",
                severity=severity,
                label=alert.level,
                description=alert.title,
                zone=None,
                recommended_actions=[
                    *alert.regulatory_actions,
                    *alert.ai_actions,
                ],
                source_detail=alert.to_dict(),
                assessed_at=assessed_at,
            )
        )

    return assessments


class RiskScoringAgent:
    """Normalize PPE and heat output for downstream agents."""

    def assess(
        self, batch: PpeDetectionBatch | HeatComplianceAlertBatch | WBGTRiskBatch
    ) -> list[RiskAssessment]:
        if isinstance(batch, PpeDetectionBatch):
            return assess_ppe(batch)
        if isinstance(batch, HeatComplianceAlertBatch):
            return assess_heat_compliance(batch)
        if isinstance(batch, WBGTRiskBatch):
            return assess_wbgt(batch)
        raise TypeError(f"Unsupported risk scoring batch: {type(batch).__name__}")
