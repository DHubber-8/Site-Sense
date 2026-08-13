from __future__ import annotations

import unittest
from datetime import datetime, timezone

from agents.heat_detection import (
    DEFAULT_SIMULATED_SOURCE_NAME,
    DEFAULT_SIMULATED_SOURCE_URL,
    SimulatedWBGTReadingSource,
    WBGTRiskAgent,
    WBGTReading,
    classify_wbgt_risk,
)


class WBGTRiskSmokeTest(unittest.TestCase):
    def test_classify_wbgt_boundary_levels(self) -> None:
        cases = [
            (27.9, "Normal"),
            (28.0, "Caution"),
            (29.9, "Caution"),
            (30.0, "High Risk"),
            (32.0, "High Risk"),
            (32.1, "Extreme"),
        ]

        for wbgt_c, expected_level in cases:
            with self.subTest(wbgt_c=wbgt_c):
                reading = WBGTReading(
                    city="Shanghai",
                    reading_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
                    air_temperature_c=33.0,
                    relative_humidity_percent=65.0,
                    wind_speed_mps=1.4,
                    wbgt_c=wbgt_c,
                    source_name=DEFAULT_SIMULATED_SOURCE_NAME,
                    source_url=DEFAULT_SIMULATED_SOURCE_URL,
                    metadata={"simulation_mode": True},
                )
                alert = classify_wbgt_risk(reading)
                self.assertEqual(alert.level, expected_level)

    def test_simulated_source_is_deterministic_with_seed(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        reading_at = datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc)

        first = source.get_reading("Shenzhen", reading_at)
        second = source.get_reading("Shenzhen", reading_at)

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_simulated_workday_profile_rises_then_dips(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)

        morning = source.get_reading("Shenzhen", datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc))
        midday = source.get_reading("Shenzhen", datetime(2026, 8, 10, 12, 15, tzinfo=timezone.utc))
        break_time = source.get_reading("Shenzhen", datetime(2026, 8, 10, 12, 45, tzinfo=timezone.utc))
        afternoon = source.get_reading("Shenzhen", datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc))

        self.assertLess(morning.wbgt_c, midday.wbgt_c)
        self.assertLess(break_time.wbgt_c, midday.wbgt_c)
        self.assertGreater(afternoon.wbgt_c, break_time.wbgt_c)

    def test_agent_returns_structured_simulated_batch(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        agent = WBGTRiskAgent(site_city="Shenzhen", reading_source=source, min_consecutive_readings=1)

        batch = agent.assess(reading_at=datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc))

        self.assertEqual(batch.reading_source_name, DEFAULT_SIMULATED_SOURCE_NAME)
        self.assertEqual(batch.reading_source_url, DEFAULT_SIMULATED_SOURCE_URL)
        self.assertEqual(len(batch.alerts), 1)
        self.assertTrue(batch.alerts[0].metadata["simulation_mode"])
        self.assertIn("wbgt_c", batch.to_dict()["alerts"][0])


if __name__ == "__main__":
    unittest.main()
