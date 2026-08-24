from __future__ import annotations

from datetime import datetime, timezone

from agents.heat_detection.schema import HeatComplianceAlertBatch, WBGTRiskBatch
from agents.ppe_detection.schema import PpeDetectionBatch

from .schema import RiskAssessment, Severity

PPE_SEVERITY_BY_LABEL: dict[str, Severity] = {
    "helmet": Severity.NONE,
    "gloves": Severity.NONE,
    "vest": Severity.NONE,
    "boots": Severity.NONE,
    "goggles": Severity.NONE,
    "person": Severity.NONE,
    "none": Severity.NONE,
    "no_helmet": Severity.CRITICAL,
    "no_boots": Severity.CRITICAL,
    "no_gloves": Severity.MODERATE,
    "no_goggle": Severity.MODERATE,
}

PPE_COVERAGE_CLASS_PAIRS: dict[str, tuple[str, str | None]] = {
    "helmet": ("helmet", "no_helmet"),
    "gloves": ("gloves", "no_gloves"),
    # The current model has no dedicated `no_vest` label. A missing vest can
    # only be surfaced via the batch-level unaccounted coverage path.
    "vest": ("vest", None),
    "boots": ("boots", "no_boots"),
    "goggles": ("goggles", "no_goggle"),
}

PPE_RECOMMENDED_ACTIONS: dict[Severity, list[str]] = {
    Severity.NONE: [
        "No action required",
    ],
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
    if severity is Severity.NONE:
        if label == "none":
            return "Generic non-PPE class from the detection model"
        return f"No actionable PPE violation: {label}"
    return f"PPE violation detected: {label} ({severity.name.lower()} severity)"


def assess_ppe(batch: PpeDetectionBatch) -> list[RiskAssessment]:
    """Convert PPE violation detections into normalized risk assessments."""

    assessed_at = datetime.now(timezone.utc)
    assessments: list[RiskAssessment] = []
    for detection in batch.detections:
        severity = PPE_SEVERITY_BY_LABEL.get(detection.item)
        if severity is None:
            raise ValueError(f"Unsupported PPE label: {detection.item}")

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


def overall_coverage_tier(assessments: list[RiskAssessment]) -> int:
    """Return a display-only PPE coverage tier derived from layer-1 outputs.

    This function intentionally reads only the normalized risk assessments already
    produced by the PPE layer, and never re-inspects the raw detection batch. That
    keeps the dashboard summary aligned with the actual alerting path while avoiding
    a second independent check that could disagree with the real-time coverage
    flags.
    """

    worn_count = 0
    has_missing_or_unaccounted = False

    for item, (positive_label, negative_label) in PPE_COVERAGE_CLASS_PAIRS.items():
        positive_seen = any(
            assessment.source == "ppe" and assessment.label == positive_label
            for assessment in assessments
        )
        negative_seen = negative_label is not None and any(
            assessment.source == "ppe" and assessment.label == negative_label
            for assessment in assessments
        )
        coverage_seen = any(
            assessment.source == "ppe_coverage" and assessment.label == item
            for assessment in assessments
        )

        if positive_seen:
            worn_count += 1
        elif negative_seen or coverage_seen:
            has_missing_or_unaccounted = True

    if worn_count == len(PPE_COVERAGE_CLASS_PAIRS) and not has_missing_or_unaccounted:
        return 4
    if worn_count <= 1:
        return 1
    if worn_count == 2:
        return 2
    return 3


def assess_ppe_coverage(batch: PpeDetectionBatch) -> list[RiskAssessment]:
    """Flag unaccounted core PPE items for manual review at batch level."""

    assessed_at = datetime.now(timezone.utc)
    observed_labels = {detection.item for detection in batch.detections}
    coverage_assessments: list[RiskAssessment] = []

    for item, (positive_label, negative_label) in PPE_COVERAGE_CLASS_PAIRS.items():
        if positive_label in observed_labels:
            continue
        if negative_label is not None and negative_label in observed_labels:
            continue

        coverage_assessments.append(
            RiskAssessment(
                source="ppe_coverage",
                severity=Severity.MINOR,
                label=item,
                description=f"Could not verify {item} - flag for manual check",
                zone=None,
                recommended_actions=list(PPE_RECOMMENDED_ACTIONS[Severity.MINOR]),
                source_detail={
                    "coverage_status": "unaccounted",
                    "item": item,
                    "positive_label": positive_label,
                    "negative_label": negative_label,
                    "observed_labels": sorted(observed_labels),
                },
                assessed_at=assessed_at,
            )
        )

    return coverage_assessments


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
            return [*assess_ppe(batch), *assess_ppe_coverage(batch)]
        if isinstance(batch, HeatComplianceAlertBatch):
            return assess_heat_compliance(batch)
        if isinstance(batch, WBGTRiskBatch):
            return assess_wbgt(batch)
        raise TypeError(f"Unsupported risk scoring batch: {type(batch).__name__}")
