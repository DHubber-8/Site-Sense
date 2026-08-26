from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .schema import HeatComplianceAlert, HeatComplianceAlertBatch

OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPENWEATHER_API_KEY_ENV = "OPENWEATHER_API_KEY"
OPENMETEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True, slots=True)
class WeatherForecastReading:
    """Normalized daily forecast input for the heat compliance alert pipeline."""

    city: str
    forecast_date: date
    max_temperature_c: float
    provider: str = "Open-Meteo"
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WeatherForecastClient(Protocol):
    def get_todays_forecast(self, city: str) -> WeatherForecastReading:
        raise NotImplementedError


def _build_openweather_request_url(base_url: str, api_key: str, city: str, units: str) -> str:
    query_string = urlencode({"q": city, "appid": api_key, "units": units})
    return f"{base_url}?{query_string}"


def _redact_openweather_source_url(request_url: str) -> str:
    parsed_url = urlsplit(request_url)
    filtered_query = [(key, value) for key, value in parse_qsl(parsed_url.query, keep_blank_values=True) if key != "appid"]
    redacted_query = urlencode(filtered_query)
    return urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, redacted_query, parsed_url.fragment))


def _build_openmeteo_geocoding_url(base_url: str, city: str = 'CN', country_code: str = 'CN') -> str:
    query_string = urlencode({"name": city, "count": 1, "language": "en", "format": "json", "country_code": country_code})
    return f"{base_url}?{query_string}"


def _build_openmeteo_forecast_url(
    base_url: str,
    latitude: float,
    longitude: float,
) -> str:
    query_string = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max",
            "timezone": "auto",
        }
    )
    return f"{base_url}?{query_string}"


def _load_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "site-sense-heat-agent/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _parse_openweather_forecast(city: str, payload: dict[str, Any], source_url: str) -> WeatherForecastReading:
    forecast_entries = payload.get("list")
    if not isinstance(forecast_entries, list) or not forecast_entries:
        raise RuntimeError("OpenWeather forecast payload did not include any forecast entries")

    city_payload = payload.get("city")
    timezone_offset_seconds = 0
    if isinstance(city_payload, dict):
        timezone_offset_seconds = int(city_payload.get("timezone", 0) or 0)

    site_timezone = timezone(timedelta(seconds=timezone_offset_seconds))
    today = datetime.now(site_timezone).date()

    max_temperatures: list[float] = []
    for entry in forecast_entries:
        if not isinstance(entry, dict):
            continue
        main_section = entry.get("main")
        if not isinstance(main_section, dict):
            continue

        temperature = main_section.get("temp_max")
        timestamp = entry.get("dt")
        if temperature is None or timestamp is None:
            continue

        temperature_c = float(temperature)
        if not math.isfinite(temperature_c):
            continue

        entry_date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone(site_timezone).date()
        if entry_date == today:
            max_temperatures.append(temperature_c)

    if not max_temperatures:
        raise RuntimeError(f"OpenWeather forecast did not include today's max temperature for {city}")

    provider_name = "OpenWeather"
    if isinstance(city_payload, dict):
        provider_name = str(city_payload.get("provider", provider_name))

    return WeatherForecastReading(
        city=city,
        forecast_date=today,
        max_temperature_c=max(max_temperatures),
        provider=provider_name,
        source_url=source_url,
        metadata={
            "timezone_offset_seconds": timezone_offset_seconds,
            "forecast_points_used": len(max_temperatures),
        },
    )


def _parse_openmeteo_geocoding(city: str, payload: dict[str, Any], source_url: str) -> dict[str, Any]:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError(f"Open-Meteo geocoding did not return coordinates for {city}")

    first_result = results[0]
    if not isinstance(first_result, dict):
        raise RuntimeError(f"Open-Meteo geocoding returned an invalid result for {city}")

    latitude = first_result.get("latitude")
    longitude = first_result.get("longitude")
    if latitude is None or longitude is None:
        raise RuntimeError(f"Open-Meteo geocoding result was missing coordinates for {city}")

    resolved_name = str(first_result.get("name", city))
    return {
        "city": resolved_name,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "source_url": source_url,
        "metadata": {
            "geocoding_name": first_result.get("name"),
            "country": first_result.get("country"),
            "admin1": first_result.get("admin1"),
            "timezone": first_result.get("timezone"),
        },
    }


def _parse_openmeteo_forecast(city: str, payload: dict[str, Any], source_url: str) -> WeatherForecastReading:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise RuntimeError(f"Open-Meteo forecast payload did not include daily temperatures for {city}")

    temperatures = daily.get("temperature_2m_max")
    dates = daily.get("time")
    if not isinstance(temperatures, list) or not temperatures:
        raise RuntimeError(f"Open-Meteo forecast payload did not include today's max temperature for {city}")
    if not isinstance(dates, list) or len(dates) != len(temperatures):
        raise RuntimeError(f"Open-Meteo forecast payload had mismatched dates and temperatures for {city}")

    max_temperature_c = float(temperatures[0])
    if not math.isfinite(max_temperature_c):
        raise RuntimeError(f"Open-Meteo forecast payload included a non-finite max temperature for {city}")

    # Open-Meteo's daily array is ordered starting today, in the site's local
    return WeatherForecastReading(
        city=city,
        forecast_date=date.fromisoformat(str(dates[0])),
        max_temperature_c=max_temperature_c,
        provider="Open-Meteo",
        source_url=source_url,
        metadata={
            "forecast_points_used": len(temperatures),
            "daily_variable": "temperature_2m_max",
        },
    )


@dataclass(slots=True)
class OpenWeatherForecastClient:
    """Fetch today's forecast maximum temperature from the OpenWeather forecast API."""

    api_key: str | None = None
    base_url: str = OPENWEATHER_FORECAST_URL
    units: str = "metric"
    timeout_seconds: float = 10.0

    def get_todays_forecast(self, city: str) -> WeatherForecastReading:
        api_key = self.api_key or os.environ.get(OPENWEATHER_API_KEY_ENV)
        if not api_key:
            raise RuntimeError(
                f"Missing weather API key. Set {OPENWEATHER_API_KEY_ENV} or pass api_key explicitly."
            )

        request_url = _build_openweather_request_url(self.base_url, api_key, city, self.units)
        payload = _load_json(request_url, self.timeout_seconds)
        source_url = _redact_openweather_source_url(request_url)
        return _parse_openweather_forecast(city, payload, source_url)


@dataclass(slots=True)
class OpenMeteoForecastClient:
    """Fetch today's forecast maximum temperature from the Open-Meteo APIs."""

    geocoding_url: str = OPENMETEO_GEOCODING_URL
    forecast_url: str = OPENMETEO_FORECAST_URL
    timeout_seconds: float = 10.0

    def get_todays_forecast(self, city: str) -> WeatherForecastReading:
        geocoding_request_url = _build_openmeteo_geocoding_url(self.geocoding_url, city)
        geocoding_payload = _load_json(geocoding_request_url, self.timeout_seconds)
        location = _parse_openmeteo_geocoding(city, geocoding_payload, geocoding_request_url)

        forecast_request_url = _build_openmeteo_forecast_url(
            self.forecast_url,
            location["latitude"],
            location["longitude"],
        )
        forecast_payload = _load_json(forecast_request_url, self.timeout_seconds)
        reading = _parse_openmeteo_forecast(location["city"], forecast_payload, forecast_request_url)
        reading.metadata.update(location["metadata"])
        return reading


def _regulatory_actions(level: str) -> list[str]:
    if level == "Level 1":
        return [
            "Implement heatstroke prevention measures",
            "Provide sufficient drinking water",
            "Have more water breaks and rest",
            "Do not arrange overtime for outdoor activities",
        ]
    if level == "Level 2":
        return [
            "Outdoor working hours must not exceed 6 hours per day",
            "Outdoor work shall not be arranged during the hottest 3 hours of the day",
            "Increase rest periods",
        ]
    if level == "Level 3":
        return ["Outdoor work should be suspended"]
    raise ValueError(f"Unsupported heat compliance level: {level}")


def _ai_actions(level: str) -> list[str]:
    if level == "Level 1":
        return [
            "Increase hydration reminders",
            "Alert site supervisor",
            "Increase monitoring frequency",
        ]
    if level == "Level 2":
        return [
            "Alert site supervisor",
            "Record worker exposure to heat duration",
            "Increase hydration breaks",
        ]
    if level == "Level 3":
        return [
            "Trigger extreme heat alert",
            "Immediate suspension of outdoor work",
            "Alert site supervisor immediately",
        ]
    raise ValueError(f"Unsupported heat compliance level: {level}")


def classify_heat_alert(reading: WeatherForecastReading) -> HeatComplianceAlert | None:
    # Classification follows taxonomy/heat_thresholds.md Section 2 directly: the
    # authoritative daily forecast maximum crossing a threshold is the whole signal.
    # There is no sustained-duration or ambient-delta concept for a once-daily forecast
    # reading (unlike the live-reading-series WBGT path) — do not reintroduce one here.
    if reading.max_temperature_c < 35.0:
        return None

    if reading.max_temperature_c < 37.0:
        level = "Level 1"
        title = "High Temperature Alert"
        threshold_min_c = 35.0
        threshold_max_c = 37.0
    elif reading.max_temperature_c < 40.0:
        level = "Level 2"
        title = "Severe Heat Alert"
        threshold_min_c = 37.0
        threshold_max_c = 40.0
    else:
        level = "Level 3"
        title = "Extreme Heat Alert"
        threshold_min_c = 40.0
        threshold_max_c = None

    return HeatComplianceAlert(
        city=reading.city,
        forecast_date=reading.forecast_date,
        forecast_max_temperature_c=reading.max_temperature_c,
        level=level,
        title=title,
        threshold_min_c=threshold_min_c,
        threshold_max_c=threshold_max_c,
        regulatory_actions=_regulatory_actions(level),
        ai_actions=_ai_actions(level),
        metadata=dict(reading.metadata),
    )


@dataclass(slots=True)
class HeatComplianceAlertAgent:
    """Compliance alert agent for daily heat forecast checks."""

    site_city: str | None = None
    weather_client: WeatherForecastClient | None = None
    weather_provider_name: str | None = None
    weather_source_url: str | None = None

    def _resolve_city(self, city: str | None) -> str:
        resolved_city = (city or self.site_city or "").strip()
        if not resolved_city:
            raise ValueError("A site city must be provided to assess heat compliance")
        return resolved_city

    def _resolve_weather_client(self) -> WeatherForecastClient:
        if self.weather_client is not None:
            return self.weather_client
        return OpenMeteoForecastClient()

    def assess(self, city: str | None = None) -> HeatComplianceAlertBatch:
        target_city = self._resolve_city(city)
        forecast = self._resolve_weather_client().get_todays_forecast(target_city)
        alert = classify_heat_alert(forecast)

        alerts = [alert] if alert is not None else []
        return HeatComplianceAlertBatch(
            site_city=forecast.city,
            forecast_date=forecast.forecast_date,
            forecast_max_temperature_c=forecast.max_temperature_c,
            alerts=alerts,
            weather_provider=self.weather_provider_name or forecast.provider,
            weather_source_url=self.weather_source_url or forecast.source_url,
        )

    def assess_many(self, cities: list[str]) -> list[HeatComplianceAlertBatch]:
        return [self.assess(city) for city in cities]