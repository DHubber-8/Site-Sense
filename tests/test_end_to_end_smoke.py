from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from agents.alert_routing import AlertRoutingAgent
from agents.heat_detection import HeatComplianceAlertAgent, WBGTReading, WBGTRiskAgent
from agents.logging import LoggingAgent
from agents.ppe_detection import PpeDetectionAgent
from agents.risk_scoring.agent import RiskScoringAgent


class _TraceReadingSource:
    def __init__(self, readings: list[WBGTReading]):
        if not readings:
            raise ValueError("readings cannot be empty")
        self._readings = list(readings)
        self._index = 0

    def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
        if self._index >= len(self._readings):
            raise RuntimeError("trace source exhausted")
        reading = self._readings[self._index]
        self._index += 1
        return reading


class EndToEndSmokeTest(unittest.TestCase):
    def _run_stage(self, name: str, operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except Exception as exc:
            self.fail(f"{name} stage failed: {type(exc).__name__}: {exc}")

    def _load_wbgt_trace(self, scenario_file: Path) -> list[WBGTReading]:
        payload = json.loads(scenario_file.read_text(encoding="utf-8"))
        readings: list[WBGTReading] = []
        for raw in payload.get("readings", []):
            readings.append(
                WBGTReading(
                    city=str(raw["city"]),
                    reading_at=datetime.fromisoformat(str(raw["reading_at"])),
                    air_temperature_c=float(raw["air_temperature_c"]),
                    relative_humidity_percent=float(raw["relative_humidity_percent"]),
                    wind_speed_mps=float(raw["wind_speed_mps"]),
                    wbgt_c=float(raw["wbgt_c"]),
                    source_name=str(raw.get("source_name", "Simulated WBGT proxy")),
                    source_url=raw.get("source_url"),
                    metadata=dict(raw.get("metadata") or {}),
                )
            )
        if not readings:
            self.fail(f"WBGT scenario has no readings: {scenario_file}")
        return readings

    def test_real_assets_pipeline_end_to_end(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        sample_dir = repository_root / "data" / "sample_images"
        scenario_dir = repository_root / "data" / "heat_proxy_or_synthetic"
        ppe_model = repository_root / str(PpeDetectionAgent().model_path)

        sample_images = sorted(
            path
            for path in sample_dir.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        self.assertTrue(sample_images, f"no sample images found in {sample_dir}")

        scenario_files = {
            "baseline": scenario_dir / "baseline.json",
            "brief_spike": scenario_dir / "brief_spike.json",
            "direct_sun_accumulation": scenario_dir / "direct_sun_accumulation.json",
            "fatigue_partial_recovery": scenario_dir / "fatigue_partial_recovery.json",
        }
        for name, path in scenario_files.items():
            self.assertTrue(path.exists(), f"missing WBGT scenario file for {name}: {path}")

        if not ppe_model.exists():
            self.skipTest(f"missing PPE checkpoint: {ppe_model}")

        try:
            import ultralytics  # noqa: F401
        except ImportError:
            self.skipTest("ultralytics is not installed; skipping end-to-end PPE inference")

        verification_lines: list[str] = []
        with tempfile.TemporaryDirectory() as temporary_directory:
            logging_agent = self._run_stage(
                "logging initialization",
                lambda: LoggingAgent(Path(temporary_directory) / "records.db"),
            )
            scoring_agent = RiskScoringAgent()
            routing_agent = AlertRoutingAgent()

            # 1) PPE over all real images.
            ppe_assessment_total = 0
            ppe_routed_total = 0
            ppe_sources_seen: set[str] = set()
            ppe_images_with_detections = 0
            ppe_agent = PpeDetectionAgent(model_path=ppe_model)
            for image_path in sample_images:
                ppe_batch = self._run_stage(
                    f"PPE detection ({image_path.name})",
                    lambda image_path=image_path: ppe_agent.detect(image_path),
                )
                if ppe_batch.detections:
                    ppe_images_with_detections += 1

                assessments = self._run_stage(
                    f"risk scoring PPE ({image_path.name})",
                    lambda ppe_batch=ppe_batch: scoring_agent.assess(ppe_batch),
                )
                routed = self._run_stage(
                    f"alert routing PPE ({image_path.name})",
                    lambda assessments=assessments: routing_agent.route_many(assessments),
                )
                self._run_stage(
                    f"logging PPE ({image_path.name})",
                    lambda routed=routed: logging_agent.record_many(routed),
                )

                ppe_assessment_total += len(assessments)
                ppe_routed_total += len(routed)
                ppe_sources_seen.update(assessment.source for assessment in assessments)

            self.assertGreater(
                ppe_images_with_detections,
                0,
                "PPE detections were empty across all sample images",
            )
            self.assertIn("ppe", ppe_sources_seen)
            self.assertIn("ppe_coverage", ppe_sources_seen)
            verification_lines.append(
                f"PPE sample_images: PASS ({len(sample_images)} images, "
                f"{ppe_images_with_detections} with detections, "
                f"{ppe_assessment_total} assessments, {ppe_routed_total} routed)"
            )

            # 2) WBGT over all four scenario files with sustained-elevation filter.
            wbgt_expected = {
                "baseline": {
                    "no_critical": True,
                },
                "brief_spike": {
                    "no_alert": True,
                },
                "direct_sun_accumulation": {
                    "needs_at_least_caution": True,
                },
                "fatigue_partial_recovery": {
                    "needs_at_least_caution": True,
                },
            }

            for scenario_name, scenario_path in scenario_files.items():
                readings = self._load_wbgt_trace(scenario_path)
                wbgt_agent = WBGTRiskAgent(
                    site_city="Shenzhen",
                    reading_source=_TraceReadingSource(readings),
                    min_consecutive_readings=3,
                )
                scenario_alert_levels: list[str] = []
                scenario_critical_alert_count = 0

                for _ in readings:
                    wbgt_batch = self._run_stage(
                        f"WBGT assess ({scenario_name})",
                        lambda wbgt_agent=wbgt_agent: wbgt_agent.assess(zone_id="zone-A"),
                    )
                    scenario_alert_levels.extend(alert.level for alert in wbgt_batch.alerts)

                    assessments = self._run_stage(
                        f"risk scoring WBGT ({scenario_name})",
                        lambda wbgt_batch=wbgt_batch: scoring_agent.assess(wbgt_batch),
                    )
                    scenario_critical_alert_count += sum(
                        1 for assessment in assessments if assessment.severity.name == "CRITICAL"
                    )

                    routed = self._run_stage(
                        f"alert routing WBGT ({scenario_name})",
                        lambda assessments=assessments: routing_agent.route_many(assessments),
                    )
                    self._run_stage(
                        f"logging WBGT ({scenario_name})",
                        lambda routed=routed: logging_agent.record_many(routed),
                    )

                if wbgt_expected[scenario_name].get("no_alert"):
                    self.assertEqual(
                        scenario_alert_levels,
                        [],
                        "brief_spike must not produce sustained WBGT alerts",
                    )
                if wbgt_expected[scenario_name].get("needs_at_least_caution"):
                    self.assertTrue(
                        any(level in {"Caution", "High Risk", "Extreme"} for level in scenario_alert_levels),
                        f"{scenario_name} must reach at least Caution-level WBGT alert",
                    )
                if wbgt_expected[scenario_name].get("no_critical"):
                    self.assertEqual(
                        scenario_critical_alert_count,
                        0,
                        "baseline must not produce Critical-tier WBGT alerts",
                    )

                verification_lines.append(
                    f"WBGT {scenario_name}: PASS ({len(readings)} readings, "
                    f"alerts={len(scenario_alert_levels)}, critical={scenario_critical_alert_count})"
                )

            # 3) Real heat-compliance network path: run when reachable, skip gracefully otherwise.
            heat_compliance_available = False
            heat_compliance_error: str | None = None
            try:
                live_heat_batch = self._run_stage(
                    "heat compliance detection (live provider)",
                    lambda: HeatComplianceAlertAgent(site_city="Shenzhen").assess(),
                )
                live_heat_assessments = self._run_stage(
                    "risk scoring heat compliance (live provider)",
                    lambda: scoring_agent.assess(live_heat_batch),
                )
                live_heat_routed = self._run_stage(
                    "alert routing heat compliance (live provider)",
                    lambda: routing_agent.route_many(live_heat_assessments),
                )
                self._run_stage(
                    "logging heat compliance (live provider)",
                    lambda: logging_agent.record_many(live_heat_routed),
                )
                heat_compliance_available = True
                verification_lines.append(
                    f"Heat compliance live provider: PASS (alerts={len(live_heat_batch.alerts)}, "
                    f"assessments={len(live_heat_assessments)}, routed={len(live_heat_routed)})"
                )
            except AssertionError:
                raise
            except Exception as exc:
                heat_compliance_error = f"{type(exc).__name__}: {exc}"
                verification_lines.append(
                    "Heat compliance live provider: SKIP "
                    f"(network/provider unavailable: {heat_compliance_error})"
                )

            # 4) Aggregate sanity checks directly from logging.
            queried_records = self._run_stage("logging query", lambda: logging_agent.recent(limit=5000))
            self.assertGreater(len(queried_records), 0, "logging should contain at least one record")
            counts_by_source: dict[str, int] = {}
            for record in queried_records:
                source = record.routed_alert.assessment.source
                counts_by_source[source] = counts_by_source.get(source, 0) + 1

            self.assertGreater(
                counts_by_source.get("ppe", 0),
                0,
                "expected at least one logged record from source=ppe",
            )
            self.assertGreater(
                counts_by_source.get("ppe_coverage", 0),
                0,
                "expected at least one logged record from source=ppe_coverage",
            )
            self.assertGreater(
                counts_by_source.get("heat_wbgt", 0),
                0,
                "expected at least one logged record from source=heat_wbgt",
            )
            if heat_compliance_available:
                self.assertGreater(
                    counts_by_source.get("heat_compliance", 0),
                    0,
                    "expected at least one logged record from source=heat_compliance",
                )

            verification_lines.append(
                "Aggregate logging: PASS "
                f"(total={len(queried_records)}, counts={counts_by_source})"
            )

        print("\n".join(verification_lines))


if __name__ == "__main__":
    unittest.main()
