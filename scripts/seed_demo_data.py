from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.alert_routing import AlertRoutingAgent
from agents.heat_detection import (
    HeatComplianceAlertAgent,
    OpenMeteoForecastClient,
    WeatherForecastReading,
    WBGTRiskAgent,
    classify_heat_alert,
)
from agents.heat_detection.schema import HeatComplianceAlertBatch
from agents.heat_detection.wbgt_risk import WBGTReading
from agents.logging import LoggingAgent
from agents.ppe_detection.agent import PpeDetectionAgent
from agents.ppe_detection.config import PPE_MODEL_PATH, resolve_trained_checkpoint
from agents.ppe_detection.schema import PpeDetectionBatch
from agents.risk_scoring.agent import RiskScoringAgent

DATABASE_PATH = REPO_ROOT / "data" / "site_sense.db"
SAMPLE_IMAGE_DIR = REPO_ROOT / "data" / "sample_images"
SAMPLE_IMAGES = sorted(
    (
        path
        for path in SAMPLE_IMAGE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ),
    key=lambda path: path.name,
)
WBGT_SCENARIOS = [
    "baseline",
    "direct_sun_accumulation",
    "brief_spike",
    "fatigue_partial_recovery",
]
PPE_SUPPORTED_LABELS = {
    "helmet",
    "gloves",
    "vest",
    "boots",
    "goggles",
    "person",
    "none",
    "no_helmet",
    "no_boots",
    "no_gloves",
    "no_goggle",
}


def _reset_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()


def _build_ppe_assessments() -> list[Any]:
    checkpoint = resolve_trained_checkpoint(REPO_ROOT)
    if checkpoint is None:
        print(
            f"  Skipping PPE: no trained checkpoint at {PPE_MODEL_PATH} or under runs/detect/."
            " Train the PPE model first (scripts/train_ppe_model.py)."
        )
        return []
    print(f"  Using PPE checkpoint: {checkpoint.relative_to(REPO_ROOT)}")
    agent = PpeDetectionAgent(model_path=checkpoint)
    scoring_agent = RiskScoringAgent()
    assessments: list[Any] = []

    for image_path in SAMPLE_IMAGES:
        if not image_path.exists():
            print(f"  Skipping missing sample image: {image_path.name}")
            continue
        try:
            batch = agent.detect(image_path)
        except Exception as exc:
            print(f"  Skipping {image_path.name}: PPE detection failed ({exc})")
            continue

        filtered_detections = [
            detection
            for detection in batch.detections
            if detection.item in PPE_SUPPORTED_LABELS
        ]

        print(f"  {image_path.name} raw detections:")
        if not filtered_detections:
            print("    none")
            continue

        core_items = {"helmet", "gloves", "vest", "boots", "goggles"}
        for detection in filtered_detections:
            direct_worn = (
                detection.item in core_items and detection.confidence >= 0.5
            )
            status = "direct_worn" if direct_worn else "other"
            print(
                "    - "
                f"{detection.item:<12s} confidence={detection.confidence:.3f} "
                f"raw_label={detection.raw_label or detection.item} status={status}"
            )

        supported_batch = PpeDetectionBatch(
            detections=filtered_detections,
            source_image=batch.source_image,
            model_name=batch.model_name,
            model_path=batch.model_path,
        )
        assessments.extend(scoring_agent.assess(supported_batch))
    return assessments


class _ReplayWBGTReadingSource:
    """Replays a fixed, pre-loaded sequence of readings, in order, for WBGTRiskAgent.

    Lets the seed script feed each scenario file's readings through the real agent —
    including its sustained-elevation false-positive filter — instead of classifying
    each reading in isolation.
    """

    def __init__(self, readings: list[WBGTReading]) -> None:
        self._readings = list(readings)
        self._index = 0

    def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
        reading = self._readings[self._index]
        self._index += 1
        return reading


def _build_wbgt_assessments() -> list[Any]:
    heat_dir = REPO_ROOT / "data" / "heat_proxy_or_synthetic"
    scoring_agent = RiskScoringAgent()
    assessments: list[Any] = []
    for scenario in WBGT_SCENARIOS:
        payload_path = heat_dir / f"{scenario}.json"
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        readings = [
            WBGTReading(
                city=str(reading_payload.get("city", "Shenzhen")),
                reading_at=datetime.fromisoformat(str(reading_payload["reading_at"])),
                air_temperature_c=float(reading_payload["air_temperature_c"]),
                relative_humidity_percent=float(
                    reading_payload["relative_humidity_percent"]
                ),
                wind_speed_mps=float(reading_payload["wind_speed_mps"]),
                wbgt_c=float(reading_payload["wbgt_c"]),
                source_name=str(
                    reading_payload.get("source_name", "Simulated WBGT proxy")
                ),
                source_url=reading_payload.get("source_url"),
                metadata=dict(reading_payload.get("metadata", {})),
            )
            for reading_payload in payload.get("readings", [])
        ]
        if not readings:
            continue

        risk_agent = WBGTRiskAgent(reading_source=_ReplayWBGTReadingSource(readings))
        for reading in readings:
            batch = risk_agent.assess(
                city=reading.city, reading_at=reading.reading_at, zone_id=scenario
            )
            if not batch.alerts:
                continue
            assessments.extend(scoring_agent.assess(batch))
    return assessments


def _build_compliance_assessments() -> list[Any]:
    scoring_agent = RiskScoringAgent()
    assessments: list[Any] = []

    for city in ["Shenzhen", "Guangzhou"]:
        try:
            batch = HeatComplianceAlertAgent(
                site_city=city, weather_client=OpenMeteoForecastClient()
            ).assess(city)
        except Exception:
            batch = None
        if batch is not None and batch.alerts:
            assessments.extend(scoring_agent.assess(batch))
            continue

        forecast_date = date(2026, 8, 10)
        reading = WeatherForecastReading(
            city=city,
            forecast_date=forecast_date,
            max_temperature_c=38.3,
            provider="Manual demo fallback",
            source_url="manual://heat-compliance-demo",
        )
        alert = classify_heat_alert(reading)
        if alert is None:
            continue
        batch = HeatComplianceAlertBatch(
            site_city=reading.city,
            forecast_date=reading.forecast_date,
            forecast_max_temperature_c=reading.max_temperature_c,
            alerts=[alert],
            weather_provider=reading.provider,
            weather_source_url=reading.source_url,
            created_at=datetime.now(timezone.utc),
        )
        assessments.extend(scoring_agent.assess(batch))
    return assessments


def _seed_database() -> list[Any]:
    all_assessments = [
        *_build_ppe_assessments(),
        *_build_wbgt_assessments(),
        *_build_compliance_assessments(),
    ]
    routed = [
        alert
        for alert in (AlertRoutingAgent().route_many(all_assessments))
        if alert is not None
    ]
    records = LoggingAgent(DATABASE_PATH).record_many(routed)
    return records


def _print_summary(records: list[Any]) -> None:
    counts = Counter()
    by_source_severity: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        assessment = record.routed_alert.assessment
        counts[(assessment.source, assessment.severity.name)] += 1
        by_source_severity[assessment.source][assessment.severity.name] += 1

    print(f"Seeded {len(records)} real pipeline alerts into {DATABASE_PATH}")
    print("Counts by source/severity:")
    for source in sorted(by_source_severity):
        print(f"  {source}: {dict(sorted(by_source_severity[source].items()))}")
    if not counts:
        print("  No routed alerts were produced by the current sample set.")


def main() -> None:
    _reset_database()
    records = _seed_database()
    _print_summary(records)


if __name__ == "__main__":
    main()
