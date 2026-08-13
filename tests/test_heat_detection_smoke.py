from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from agents.heat_detection import (
    HeatComplianceAlertAgent,
    OpenMeteoForecastClient,
    WeatherForecastReading,
    classify_heat_alert,
)

from agents.heat_detection.agent import (
    OPENMETEO_GEOCODING_URL,
    _build_openmeteo_geocoding_url,
)

class _FakeWeatherClient:
    def __init__(self, reading: WeatherForecastReading):
        self._reading = reading

    def get_todays_forecast(self, city: str) -> WeatherForecastReading:
        return WeatherForecastReading(
            city=city,
            forecast_date=self._reading.forecast_date,
            max_temperature_c=self._reading.max_temperature_c,
            provider=self._reading.provider,
            source_url=self._reading.source_url,
            metadata=dict(self._reading.metadata),
        )


class HeatDetectionSmokeTest(unittest.TestCase):
    def test_classify_heat_alert_boundary_levels(self) -> None:
        cases = [
            (34.9, None),
            (35.0, "Level 1"),
            (36.9, "Level 1"),
            (37.0, "Level 2"),
            (39.9, "Level 2"),
            (40.0, "Level 3"),
        ]

        for temperature, expected_level in cases:
            with self.subTest(temperature=temperature):
                reading = WeatherForecastReading(
                    city="Shanghai",
                    forecast_date=date(2026, 8, 10),
                    max_temperature_c=temperature,
                )
                alert = classify_heat_alert(reading)

                if expected_level is None:
                    self.assertIsNone(alert)
                else:
                    self.assertIsNotNone(alert)
                    assert alert is not None
                    self.assertEqual(alert.level, expected_level)

    def test_assess_returns_structured_batch(self) -> None:
        reading = WeatherForecastReading(
            city="Guangzhou",
            forecast_date=date(2026, 8, 10),
            max_temperature_c=37.5,
            provider="OpenWeather",
            source_url="https://example.test/weather",
            metadata={"forecast_points_used": 4},
        )
        agent = HeatComplianceAlertAgent(
            site_city="Guangzhou",
            weather_client=_FakeWeatherClient(reading),
        )

        batch = agent.assess()

        self.assertEqual(batch.site_city, "Guangzhou")
        self.assertEqual(batch.forecast_max_temperature_c, 37.5)
        self.assertEqual(batch.weather_provider, "OpenWeather")
        self.assertEqual(batch.weather_source_url, "https://example.test/weather")
        self.assertEqual(len(batch.alerts), 1)
        alert_payload = batch.alerts[0].to_dict()
        self.assertEqual(alert_payload["level"], "Level 2")
        self.assertIn("regulatory_actions", alert_payload)
        self.assertIn("ai_actions", alert_payload)

    def test_assess_keeps_forecast_summary_when_below_threshold(self) -> None:
        reading = WeatherForecastReading(
            city="Nanjing",
            forecast_date=date(2026, 8, 10),
            max_temperature_c=34.0,
        )
        agent = HeatComplianceAlertAgent(
            site_city="Nanjing",
            weather_client=_FakeWeatherClient(reading),
        )

        batch = agent.assess()

        self.assertEqual(batch.forecast_max_temperature_c, 34.0)
        self.assertEqual(batch.alerts, [])

    def test_default_weather_client_uses_open_meteo(self) -> None:
        agent = HeatComplianceAlertAgent(site_city="Hangzhou")

        self.assertIsInstance(agent._resolve_weather_client(), OpenMeteoForecastClient)

    def test_geocoding_request_includes_country_filter(self) -> None:
        url = _build_openmeteo_geocoding_url(OPENMETEO_GEOCODING_URL, "Shenzhen")
        self.assertIn("country_code=CN", url)
    
    def test_open_meteo_client_returns_today_forecast(self) -> None:
        geocoding_payload = {
            "results": [
                {
                    "name": "Shenzhen",
                    "latitude": 22.5431,
                    "longitude": 114.0579,
                    "country": "China",
                    "admin1": "Guangdong",
                    "timezone": "Asia/Shanghai",
                }
            ]
        }
        forecast_payload = {
            "daily": {
                "time": ["2026-08-10"],
                "temperature_2m_max": [41.2],
            }
        }

        with patch("agents.heat_detection.agent._load_json", side_effect=[geocoding_payload, forecast_payload]):
            client = OpenMeteoForecastClient()
            reading = client.get_todays_forecast("Shenzhen")

        self.assertEqual(reading.city, "Shenzhen")
        self.assertEqual(reading.provider, "Open-Meteo")
        self.assertEqual(reading.max_temperature_c, 41.2)
        self.assertEqual(reading.metadata["daily_variable"], "temperature_2m_max")

    def test_open_meteo_client_raises_on_empty_geocoding_results(self) -> None:
        with patch("agents.heat_detection.agent._load_json", return_value={"results": []}):
            client = OpenMeteoForecastClient()
            with self.assertRaises(RuntimeError):
                client.get_todays_forecast("Nowhere City")

    def test_open_meteo_client_raises_on_missing_daily_data(self) -> None:
        geocoding_payload = {"results": [{"name": "Wuhan", "latitude": 30.6, "longitude": 114.3}]}
        with patch("agents.heat_detection.agent._load_json", side_effect=[geocoding_payload, {}]):
            client = OpenMeteoForecastClient()
            with self.assertRaises(RuntimeError):
                client.get_todays_forecast("Wuhan")

    def test_open_meteo_client_raises_on_mismatched_date_temperature_lengths(self) -> None:
        geocoding_payload = {"results": [{"name": "Wuhan", "latitude": 30.6, "longitude": 114.3}]}
        forecast_payload = {"daily": {"time": ["2026-08-10", "2026-08-11"], "temperature_2m_max": [38.0]}}
        with patch("agents.heat_detection.agent._load_json", side_effect=[geocoding_payload, forecast_payload]):
            client = OpenMeteoForecastClient()
            with self.assertRaises(RuntimeError):
                client.get_todays_forecast("Wuhan")

    def test_wbgt_agent_single_spike_does_not_alert(self) -> None:
        readings = [
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
                air_temperature_c=30.0,
                relative_humidity_percent=60.0,
                wind_speed_mps=2.0,
                wbgt_c=27.0,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
                air_temperature_c=31.0,
                relative_humidity_percent=62.0,
                wind_speed_mps=1.8,
                wbgt_c=27.5,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc),
                air_temperature_c=36.0,
                relative_humidity_percent=69.0,
                wind_speed_mps=1.5,
                wbgt_c=34.5,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
        ]

        class _PatternSource:
            def __init__(self, items):
                self._items = list(items)
                self._index = 0

            def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
                item = self._items[self._index]
                self._index += 1
                return item

        agent = WBGTRiskAgent(
            site_city="Guangzhou",
            reading_source=_PatternSource(readings),
            min_consecutive_readings=3,
        )

        for _ in readings:
            batch = agent.assess(zone_id="zone-A")

        self.assertEqual(batch.alerts, [])

    def test_wbgt_agent_sustained_elevated_pattern_alerts(self) -> None:
        readings = [
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
                air_temperature_c=30.0,
                relative_humidity_percent=60.0,
                wind_speed_mps=2.0,
                wbgt_c=27.0,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
                air_temperature_c=32.0,
                relative_humidity_percent=66.0,
                wind_speed_mps=1.6,
                wbgt_c=29.5,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc),
                air_temperature_c=33.5,
                relative_humidity_percent=68.0,
                wind_speed_mps=1.4,
                wbgt_c=30.8,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
            WBGTReading(
                city="Guangzhou",
                reading_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
                air_temperature_c=34.8,
                relative_humidity_percent=70.0,
                wind_speed_mps=1.2,
                wbgt_c=31.6,
                source_name="Simulated WBGT proxy",
                source_url="simulated://wbgt",
            ),
        ]

        class _PatternSource:
            def __init__(self, items):
                self._items = list(items)
                self._index = 0

            def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
                item = self._items[self._index]
                self._index += 1
                return item

        agent = WBGTRiskAgent(
            site_city="Guangzhou",
            reading_source=_PatternSource(readings),
            min_consecutive_readings=3,
        )

        for _ in readings[:-1]:
            batch = agent.assess(zone_id="zone-A")
            self.assertEqual(batch.alerts, [])

        batch = agent.assess(zone_id="zone-A")

        self.assertEqual(len(batch.alerts), 1)
        self.assertIn(batch.alerts[0].level, {"Caution", "High Risk", "Extreme"})

    def test_wbgt_agent_returns_simulated_risk_level(self) -> None:
        agent = WBGTRiskAgent(
            site_city="Guangzhou",
            reading_source=SimulatedWBGTReadingSource(seed=42),
        )

        batch = agent.assess(reading_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc), zone_id="zone-A")

        self.assertEqual(batch.site_city, "Guangzhou")
        self.assertEqual(batch.reading_source_name, "Simulated WBGT proxy")
        self.assertIn("level", batch.alerts[0].to_dict()) if batch.alerts else self.assertEqual(batch.alerts, [])

    def test_wbgt_agent_can_use_custom_reading_source(self) -> None:
        class _FixedWBGTSource:
            def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
                return WBGTReading(
                    city=city,
                    reading_at=reading_at or datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc),
                    air_temperature_c=35.0,
                    relative_humidity_percent=70.0,
                    wind_speed_mps=1.2,
                    wbgt_c=31.5,
                    source_name="Simulated WBGT proxy",
                    source_url="simulated://wbgt",
                    metadata={"simulation_mode": True},
                )

        agent = WBGTRiskAgent(site_city="Shenzhen", reading_source=_FixedWBGTSource(), min_consecutive_readings=1)
        batch = agent.assess(zone_id="zone-1")

        self.assertEqual(batch.alerts[0].level, "High Risk")

if __name__ == "__main__":
    unittest.main()