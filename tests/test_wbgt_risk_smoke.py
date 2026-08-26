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

        morning = source.get_reading(
            "Shenzhen", datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        )
        midday = source.get_reading(
            "Shenzhen", datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
        )
        break_time = source.get_reading(
            "Shenzhen", datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc)
        )
        afternoon = source.get_reading(
            "Shenzhen", datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
        )

        self.assertLess(morning.wbgt_c, midday.wbgt_c)
        self.assertLess(break_time.wbgt_c, midday.wbgt_c)
        self.assertGreater(afternoon.wbgt_c, break_time.wbgt_c)

    def test_agent_returns_structured_simulated_batch(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        agent = WBGTRiskAgent(
            site_city="Shenzhen", reading_source=source, min_consecutive_readings=1
        )

        batch = agent.assess(
            reading_at=datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(batch.reading_source_name, DEFAULT_SIMULATED_SOURCE_NAME)
        self.assertEqual(batch.reading_source_url, DEFAULT_SIMULATED_SOURCE_URL)
        self.assertEqual(len(batch.alerts), 1)
        self.assertTrue(batch.alerts[0].metadata["simulation_mode"])
        self.assertIn("wbgt_c", batch.to_dict()["alerts"][0])

    def test_generate_workday_trace_scenarios_are_seed_deterministic(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)

        first = source.generate_workday_trace(
            "Shenzhen",
            reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            sample_count=19,
            scenario="direct_sun_accumulation",
        )
        second = source.generate_workday_trace(
            "Shenzhen",
            reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            sample_count=19,
            scenario="direct_sun_accumulation",
        )

        self.assertEqual(
            [item.to_dict() for item in first], [item.to_dict() for item in second]
        )

    def test_direct_sun_accumulation_trace_shape_and_range(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        trace = source.generate_workday_trace(
            "Shenzhen",
            reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            sample_count=19,
            scenario="direct_sun_accumulation",
        )

        wbgt = [item.wbgt_c for item in trace]
        early_gain = wbgt[4] - wbgt[2]  # 10:00 - 09:00
        later_gain = wbgt[6] - wbgt[4]  # 11:00 - 10:00

        self.assertGreater(later_gain, early_gain)
        self.assertLess(wbgt[9], wbgt[8])  # 12:30 is lower than 12:00 due to break drop
        self.assertGreaterEqual(max(wbgt), 30.0)

    def test_brief_spike_does_not_trigger_sustained_alert(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        trace = source.generate_workday_trace(
            "Shenzhen",
            reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            sample_count=37,
            scenario="brief_spike",
        )

        class _TraceSource:
            def __init__(self, items: list[WBGTReading]) -> None:
                self._items = items
                self._index = 0

            def get_reading(
                self, city: str, reading_at: datetime | None = None
            ) -> WBGTReading:
                item = self._items[self._index]
                self._index += 1
                return item

        agent = WBGTRiskAgent(
            site_city="Shenzhen",
            reading_source=_TraceSource(trace),
            min_consecutive_readings=3,
        )

        alerts_seen = []
        for _ in trace:
            batch = agent.assess(zone_id="zone-A")
            alerts_seen.extend(batch.alerts)

        self.assertGreaterEqual(max(item.wbgt_c for item in trace), 28.0)
        self.assertEqual(alerts_seen, [])

    def test_fatigue_partial_recovery_trace_shape_and_range(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)
        trace = source.generate_workday_trace(
            "Shenzhen",
            reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
            sample_count=37,
            scenario="fatigue_partial_recovery",
        )

        wbgt = [item.wbgt_c for item in trace]
        fatigue_curve = [
            item.metadata["simulation_profile"]["scenario_curve"] for item in trace
        ]

        self.assertGreater(fatigue_curve[11], fatigue_curve[9])  # First rise.
        self.assertLess(
            fatigue_curve[12], fatigue_curve[11]
        )  # First partial-recovery dip.
        self.assertGreater(fatigue_curve[12], 0.0)  # Dip does not recover to baseline.
        self.assertGreater(fatigue_curve[15], fatigue_curve[13])  # Second rise.
        self.assertLess(
            fatigue_curve[16], fatigue_curve[15]
        )  # Second partial-recovery dip.
        self.assertGreater(fatigue_curve[19], fatigue_curve[17])  # Third rise.
        self.assertGreaterEqual(max(wbgt), 30.0)

    def test_generate_workday_trace_rejects_unknown_scenario(self) -> None:
        source = SimulatedWBGTReadingSource(seed=17)

        with self.assertRaises(ValueError):
            source.generate_workday_trace(
                "Shenzhen",
                reading_date=datetime(2026, 8, 10, tzinfo=timezone.utc).date(),
                sample_count=6,
                scenario="unknown_profile",
            )


if __name__ == "__main__":
    unittest.main()
