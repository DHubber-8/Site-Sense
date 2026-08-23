from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agents.alert_routing import AlertRoutingAgent
from agents.heat_detection import HeatComplianceAlertAgent, WeatherForecastReading
from agents.logging import LoggingAgent
from agents.ppe_detection import PpeDetectionAgent
from agents.risk_scoring.agent import RiskScoringAgent


class _SyntheticWeatherClient:
    def get_todays_forecast(self, city: str) -> WeatherForecastReading:
        return WeatherForecastReading(
            city=city,
            forecast_date=date(2026, 8, 23),
            max_temperature_c=37.5,
            provider="Synthetic test forecast",
            source_url="synthetic://heat-compliance",
            metadata={
                "elevated_duration_minutes": 45,
                "ambient_temperature_c": 30.0,
            },
        )


class EndToEndSmokeTest(unittest.TestCase):
    def _run_stage(self, name: str, operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except Exception as exc:
            self.fail(f"{name} stage failed: {type(exc).__name__}: {exc}")

    def test_real_ppe_and_heat_batches_reach_logging(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        sample_image = repository_root / "data" / "sample_images" / "image1132.jpg"
        ppe_model = (
            repository_root / "runs" / "detect" / "train-10" / "weights" / "best.pt"
        )
        self.assertTrue(sample_image.exists(), f"missing sample image: {sample_image}")
        self.assertTrue(ppe_model.exists(), f"missing PPE checkpoint: {ppe_model}")

        ppe_batch = self._run_stage(
            "PPE detection",
            lambda: PpeDetectionAgent(model_path=ppe_model).detect(sample_image),
        )
        self.assertTrue(
            ppe_batch.detections, "PPE detection stage returned no detections"
        )

        heat_batch = self._run_stage(
            "heat compliance detection",
            lambda: HeatComplianceAlertAgent(
                site_city="Synthetic Site",
                weather_client=_SyntheticWeatherClient(),
            ).assess(),
        )
        self.assertEqual(len(heat_batch.alerts), 1)
        self.assertEqual(heat_batch.alerts[0].level, "Level 2")

        scoring_agent = RiskScoringAgent()
        risk_assessments = self._run_stage(
            "risk scoring",
            lambda: scoring_agent.assess(ppe_batch) + scoring_agent.assess(heat_batch),
        )
        self.assertTrue(risk_assessments, "risk scoring stage returned no assessments")

        routed_alerts = self._run_stage(
            "alert routing",
            lambda: AlertRoutingAgent().route_many(risk_assessments),
        )
        self.assertTrue(routed_alerts, "alert routing stage returned no routed alerts")

        with tempfile.TemporaryDirectory() as temporary_directory:
            logging_agent = self._run_stage(
                "logging initialization",
                lambda: LoggingAgent(Path(temporary_directory) / "records.db"),
            )
            records = self._run_stage(
                "logging record",
                lambda: logging_agent.record_many(routed_alerts),
            )
            queried_records = self._run_stage(
                "logging query",
                logging_agent.recent,
            )

        self.assertEqual(len(records), len(routed_alerts))
        self.assertEqual(len(queried_records), len(routed_alerts))
        self.assertEqual(
            {record.routed_alert.assessment.source for record in queried_records},
            {"ppe", "heat_compliance"},
        )


if __name__ == "__main__":
    unittest.main()
