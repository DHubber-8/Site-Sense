from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from agents.heat_detection import (
    HeatComplianceAlertAgent,
    OpenMeteoForecastClient,
    OpenWeatherForecastClient,
    WeatherForecastReading,
    classify_heat_alert,
)

from agents.heat_detection.agent import (
    OPENWEATHER_API_KEY_ENV,
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
                    metadata={"elevated_duration_minutes": 30, "ambient_temperature_c": 30.0},
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
            metadata={"forecast_points_used": 4, "elevated_duration_minutes": 45, "ambient_temperature_c": 30.0},
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

    def test_classify_heat_alert_requires_proxy_safeguards(self) -> None:
        cases = [
            ({"elevated_duration_minutes": 15, "ambient_temperature_c": 30.0}, None),
            ({"elevated_duration_minutes": 45, "ambient_temperature_c": 34.6}, None),
        ]

        for metadata, expected_level in cases:
            with self.subTest(metadata=metadata):
                reading = WeatherForecastReading(
                    city="Shanghai",
                    forecast_date=date(2026, 8, 10),
                    max_temperature_c=37.5,
                    metadata=metadata,
                )
                alert = classify_heat_alert(reading)

                if expected_level is None:
                    self.assertIsNone(alert)
                else:
                    self.assertIsNotNone(alert)

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

    def test_openweather_client_skips_non_finite_temperatures(self) -> None:
        today_timestamp = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "list": [
                {"dt": today_timestamp, "main": {"temp_max": float("inf")}},
                {"dt": today_timestamp, "main": {"temp_max": float("nan")}},
                {"dt": today_timestamp, "main": {"temp_max": 41.2}},
            ],
            "city": {"timezone": 0, "provider": "OpenWeather"},
        }

        with patch.dict(os.environ, {OPENWEATHER_API_KEY_ENV: "super-secret"}, clear=False):
            with patch("agents.heat_detection.agent._load_json", return_value=payload):
                client = OpenWeatherForecastClient()
                reading = client.get_todays_forecast("Shenzhen")

        self.assertEqual(reading.max_temperature_c, 41.2)
        self.assertEqual(reading.metadata["forecast_points_used"], 1)

    def test_openweather_client_redacts_api_key_from_source_url(self) -> None:
        captured_source_urls: list[str] = []

        def fake_parse(city: str, payload: dict[str, object], source_url: str) -> WeatherForecastReading:
            captured_source_urls.append(source_url)
            return WeatherForecastReading(
                city=city,
                forecast_date=date(2026, 8, 10),
                max_temperature_c=41.2,
                provider="OpenWeather",
                source_url=source_url,
                metadata={"timezone_offset_seconds": 28800},
            )

        with patch.dict(os.environ, {OPENWEATHER_API_KEY_ENV: "super-secret"}, clear=False):
            with patch("agents.heat_detection.agent._load_json", return_value={}) as load_json:
                with patch("agents.heat_detection.agent._parse_openweather_forecast", side_effect=fake_parse):
                    client = OpenWeatherForecastClient()
                    reading = client.get_todays_forecast("Shenzhen")

        request_url = load_json.call_args.args[0]
        self.assertIn("appid=super-secret", request_url)
        self.assertEqual(captured_source_urls, [reading.source_url])
        self.assertNotIn("appid=", reading.source_url or "")
        self.assertIn("q=Shenzhen", reading.source_url or "")

        agent = HeatComplianceAlertAgent(
            site_city="Shenzhen",
            weather_client=_FakeWeatherClient(reading),
        )
        batch = agent.assess()

        self.assertEqual(batch.weather_source_url, reading.source_url)
        serialized = batch.to_dict()
        self.assertEqual(serialized["weather_source_url"], reading.source_url)
        self.assertNotIn("appid=", serialized["weather_source_url"] or "")

    def test_open_meteo_client_rejects_non_finite_temperatures(self) -> None:
        geocoding_payload = {"results": [{"name": "Wuhan", "latitude": 30.6, "longitude": 114.3}]}
        forecast_payload = {"daily": {"time": ["2026-08-10"], "temperature_2m_max": [float("nan")]}}
        with patch("agents.heat_detection.agent._load_json", side_effect=[geocoding_payload, forecast_payload]):
            client = OpenMeteoForecastClient()
            with self.assertRaises(RuntimeError):
                client.get_todays_forecast("Wuhan")

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

if __name__ == "__main__":
    unittest.main()