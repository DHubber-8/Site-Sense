from __future__ import annotations

# SIMULATED OUTPUT ONLY: this module intentionally models a deterministic WBGT
# proxy for testing and workflow design. It is not live sensor data and must
# not be presented as a real thermal-camera or physical sensor feed.
import hashlib
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, time, timezone
from typing import Any, Protocol

from .schema import WBGTRiskAlert, WBGTRiskBatch

WBGT_NORMAL_THRESHOLD_C = 28.0
WBGT_CAUTION_THRESHOLD_C = 30.0
WBGT_HIGH_RISK_THRESHOLD_C = 32.0

DEFAULT_SIMULATED_SOURCE_NAME = "Simulated WBGT proxy"
DEFAULT_SIMULATED_SOURCE_URL = "simulated://wbgt"
WBGT_SCENARIOS = {
    "baseline",
    "direct_sun_accumulation",
    "brief_spike",
    "fatigue_partial_recovery",
}


@dataclass(frozen=True, slots=True)
class WBGTReading:
    """A single simulated WBGT proxy reading for Section 1 classification.

    This is synthetic output used for testing and workflow design; it is not a
    live sensor reading from a physical WBGT device or thermal camera.
    """

    city: str
    reading_at: datetime
    air_temperature_c: float
    relative_humidity_percent: float
    wind_speed_mps: float
    wbgt_c: float
    source_name: str = DEFAULT_SIMULATED_SOURCE_NAME
    source_url: str | None = DEFAULT_SIMULATED_SOURCE_URL
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "city": self.city,
            "reading_at": self.reading_at.isoformat(),
            "air_temperature_c": self.air_temperature_c,
            "relative_humidity_percent": self.relative_humidity_percent,
            "wind_speed_mps": self.wind_speed_mps,
            "wbgt_c": self.wbgt_c,
            "source_name": self.source_name,
            "source_url": self.source_url,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class WBGTReadingSource(Protocol):
    def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
        raise NotImplementedError


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _ensure_aware(reading_at: datetime | None) -> datetime:
    if reading_at is None:
        return datetime.now(timezone.utc)
    if reading_at.tzinfo is None:
        return reading_at.replace(tzinfo=timezone.utc)
    return reading_at.astimezone(timezone.utc)


def _validate_wbgt_scenario(scenario: str) -> str:
    normalized = scenario.strip().lower()
    if normalized not in WBGT_SCENARIOS:
        allowed = ", ".join(sorted(WBGT_SCENARIOS))
        raise ValueError(f"Unsupported WBGT scenario '{scenario}'. Supported scenarios: {allowed}")
    return normalized


def _stull_wet_bulb_temperature(air_temperature_c: float, relative_humidity_percent: float) -> float:
    humidity = _clamp(relative_humidity_percent, 1.0, 100.0)
    return (
        air_temperature_c * math.atan(0.151977 * math.sqrt(humidity + 8.313659))
        + math.atan(air_temperature_c + humidity)
        - math.atan(humidity - 1.676331)
        + 0.00391838 * (humidity ** 1.5) * math.atan(0.023101 * humidity)
        - 4.686035
    )


def compute_wbgt(air_temperature_c: float, relative_humidity_percent: float, wind_speed_mps: float, solar_load: float) -> float:
    """Compute a simulated WBGT-like proxy from synthetic environmental inputs.

    This is not a live sensor model and should be treated as simulated output
    only, even when the data shape is compatible with a real sensor contract.
    """

    wet_bulb_c = _stull_wet_bulb_temperature(air_temperature_c, relative_humidity_percent)
    globe_temperature_c = air_temperature_c + solar_load - (0.7 * wind_speed_mps)
    return 0.7 * wet_bulb_c + 0.2 * air_temperature_c + 0.1 * globe_temperature_c


def _regularity_actions(level: str) -> list[str]:
    if level == "Normal":
        return ["Continue normal work and routine monitoring"]
    if level == "Caution":
        return ["Increase hydration and more breaks"]
    if level == "High Risk":
        return ["Reduce workload", "Increase rest frequency", "Monitor worker temperature closely"]
    if level == "Extreme":
        return ["Recommend suspension of heavy outdoor work", "Move workers to a shaded or cooler area"]
    raise ValueError(f"Unsupported WBGT level: {level}")


def _ai_actions(level: str) -> list[str]:
    if level == "Normal":
        return ["Maintain routine monitoring"]
    if level == "Caution":
        return ["Increase hydration reminders", "Schedule additional breaks"]
    if level == "High Risk":
        return ["Reduce work intensity", "Increase monitoring frequency"]
    if level == "Extreme":
        return ["Trigger extreme heat alert", "Suspend heavy outdoor work"]
    raise ValueError(f"Unsupported WBGT level: {level}")


def _classify_wbgt_level(wbgt_c: float) -> tuple[str, str, float, float | None]:
    if wbgt_c < WBGT_NORMAL_THRESHOLD_C:
        return "Normal", "Normal Heat Risk", 0.0, WBGT_NORMAL_THRESHOLD_C
    if wbgt_c < WBGT_CAUTION_THRESHOLD_C:
        return "Caution", "Heat Caution", WBGT_NORMAL_THRESHOLD_C, WBGT_CAUTION_THRESHOLD_C
    if wbgt_c <= WBGT_HIGH_RISK_THRESHOLD_C:
        return "High Risk", "High Heat Risk", WBGT_CAUTION_THRESHOLD_C, WBGT_HIGH_RISK_THRESHOLD_C
    return "Extreme", "Extreme Heat Risk", WBGT_HIGH_RISK_THRESHOLD_C, None


def _has_sustained_elevation(
    readings: list[WBGTReading],
    elevated_threshold_c: float = WBGT_NORMAL_THRESHOLD_C,
    min_consecutive_readings: int = 3,
) -> bool:
    # False-positive guard: a single hot reading may be a transient spike from a
    # brief shade change or gust, but sustained exposure across several readings
    # is the signal we use before escalating a worker-zone risk alert.
    if min_consecutive_readings <= 1:
        return True
    if len(readings) < min_consecutive_readings:
        return False

    consecutive = 0
    for reading in reversed(readings):
        if reading.wbgt_c >= elevated_threshold_c:
            consecutive += 1
            if consecutive >= min_consecutive_readings:
                return True
        else:
            consecutive = 0
    return False


def classify_wbgt_risk(reading: WBGTReading) -> WBGTRiskAlert:
    # SIMULATED OUTPUT ONLY: the classification is based on the synthetic WBGT
    # proxy produced in this module, not on a live field measurement.
    level, title, threshold_min_c, threshold_max_c = _classify_wbgt_level(reading.wbgt_c)
    return WBGTRiskAlert(
        city=reading.city,
        reading_at=reading.reading_at,
        wbgt_c=reading.wbgt_c,
        level=level,
        title=title,
        threshold_min_c=threshold_min_c,
        threshold_max_c=threshold_max_c,
        regulatory_actions=_regularity_actions(level),
        ai_actions=_ai_actions(level),
        metadata=dict(reading.metadata),
    )


@dataclass(slots=True)
class SimulatedWBGTReadingSource:
    """Deterministic WBGT proxy generator for tests and demo workflows.

    The emitted readings are simulated proxy output only. They are not live
    thermal-camera or physical WBGT sensor data.
    """

    seed: int = 7
    source_name: str = DEFAULT_SIMULATED_SOURCE_NAME
    source_url: str | None = DEFAULT_SIMULATED_SOURCE_URL
    workday_start: time = time(8, 0)
    workday_end: time = time(17, 0)
    break_start: time = time(12, 0)
    break_end: time = time(13, 0)

    def _profile_seed(self, city: str, reading_date: date) -> int:
        seed_material = f"{self.seed}:{city}:{reading_date.isoformat()}".encode("utf-8")
        return int.from_bytes(hashlib.sha256(seed_material).digest(), "big")

    def _profile_parameters(self, city: str, reading_date: date) -> dict[str, float]:
        rng = random.Random(self._profile_seed(city, reading_date))
        return {
            "temp_base": 30.0 + rng.uniform(-1.0, 1.5),
            "temp_amp": 4.2 + rng.uniform(0.0, 1.8),
            "humidity_base": 62.0 + rng.uniform(-6.0, 8.0),
            "humidity_amp": 9.0 + rng.uniform(0.0, 6.0),
            "wind_base": 1.4 + rng.uniform(-0.3, 0.6),
            "wind_amp": 0.7 + rng.uniform(0.0, 0.6),
            "break_cooling": 1.2 + rng.uniform(0.2, 0.9),
            "break_humidity_bump": 2.0 + rng.uniform(0.0, 4.0),
            "break_wind_bump": 0.3 + rng.uniform(0.0, 0.8),
            "phase": rng.uniform(0.0, 2.0 * math.pi),
            "solar_load": 1.7 + rng.uniform(0.2, 1.2),
        }

    def _workday_fraction(self, reading_at: datetime) -> float:
        start_minutes = self.workday_start.hour * 60 + self.workday_start.minute
        end_minutes = self.workday_end.hour * 60 + self.workday_end.minute
        current_minutes = reading_at.hour * 60 + reading_at.minute + (reading_at.second / 60.0)
        span = max(1.0, float(end_minutes - start_minutes))
        return _clamp((current_minutes - start_minutes) / span, 0.0, 1.0)

    def _break_fraction(self, reading_at: datetime) -> float:
        break_start_minutes = self.break_start.hour * 60 + self.break_start.minute
        break_end_minutes = self.break_end.hour * 60 + self.break_end.minute
        current_minutes = reading_at.hour * 60 + reading_at.minute + (reading_at.second / 60.0)
        midpoint = (break_start_minutes + break_end_minutes) / 2.0
        width = max(15.0, (break_end_minutes - break_start_minutes) / 2.0)
        distance = abs(current_minutes - midpoint)
        return math.exp(-((distance / width) ** 2))

    def _scenario_modifier(
        self,
        reading_at: datetime,
        progress: float,
        break_curve: float,
        scenario: str,
    ) -> tuple[float, float, float, float, dict[str, float]]:
        if scenario == "baseline":
            return 0.0, 0.0, 0.0, 0.0, {"scenario_curve": 0.0}

        if scenario == "direct_sun_accumulation":
            concave_rise = progress ** 2.2
            sharp_break_drop = break_curve ** 0.45
            return (
                (5.1 * concave_rise) - (4.2 * sharp_break_drop),
                (-8.0 * concave_rise) + (4.8 * sharp_break_drop),
                (-0.65 * concave_rise) + (0.9 * sharp_break_drop),
                (3.0 * concave_rise) - (2.9 * sharp_break_drop),
                {
                    "scenario_curve": concave_rise,
                    "scenario_break_drop": sharp_break_drop,
                },
            )

        if scenario == "brief_spike":
            # A short-lived local hotspot with immediate return to a cooler baseline.
            spike_center = 0.5556
            spike_width = 0.022
            spike = math.exp(-(((progress - spike_center) / spike_width) ** 2))
            return (
                -2.6 + (4.5 * spike),
                2.2 - (3.6 * spike),
                0.35 - (0.45 * spike),
                -1.1 + (2.1 * spike),
                {
                    "scenario_curve": spike,
                    "scenario_spike_center": spike_center,
                    "scenario_spike_width": spike_width,
                },
            )

        if scenario == "fatigue_partial_recovery":
            start_minutes = self.workday_start.hour * 60 + self.workday_start.minute
            current_minutes = reading_at.hour * 60 + reading_at.minute + (reading_at.second / 60.0)
            minutes_since_start = current_minutes - start_minutes

            cycle_start = 120.0
            cycle_end = 285.0
            load = 0.0
            if minutes_since_start < cycle_start:
                load = 0.0
            elif minutes_since_start <= cycle_end:
                local = minutes_since_start - cycle_start
                if local <= 45.0:
                    load = local / 45.0
                elif local <= 60.0:
                    # First rest dip: recover partially, never back to baseline.
                    load = 1.0 - ((local - 45.0) / 15.0) * 0.4
                elif local <= 105.0:
                    load = 0.6 + ((local - 60.0) / 45.0) * 1.0
                elif local <= 120.0:
                    # Second rest dip: still above the first-cycle baseline.
                    load = 1.6 - ((local - 105.0) / 15.0) * 0.5
                else:
                    load = 1.1 + ((local - 120.0) / 45.0) * 1.0
            else:
                # Residual fatigue remains elevated through the afternoon.
                tail_progress = _clamp((minutes_since_start - cycle_end) / 120.0, 0.0, 1.0)
                load = 2.1 - 0.7 * tail_progress

            return (
                2.1 * load,
                -2.6 * load,
                -0.25 * load,
                1.5 * load,
                {"scenario_curve": load},
            )

        # Kept defensive even though caller validates scenario names.
        return 0.0, 0.0, 0.0, 0.0, {"scenario_curve": 0.0}

    def _simulate_environment(self, city: str, reading_at: datetime, scenario: str = "baseline") -> tuple[float, float, float, dict[str, float]]:
        reading_date = reading_at.date()
        profile = self._profile_parameters(city, reading_date)
        progress = self._workday_fraction(reading_at)
        break_curve = self._break_fraction(reading_at)
        sun_curve = math.sin(math.pi * progress) ** 1.35
        wobble = math.sin((2.0 * math.pi * progress) + profile["phase"])
        normalized_scenario = _validate_wbgt_scenario(scenario)
        temp_delta, humidity_delta, wind_delta, solar_delta, scenario_metadata = self._scenario_modifier(
            reading_at,
            progress,
            break_curve,
            normalized_scenario,
        )

        air_temperature_c = (
            profile["temp_base"]
            + profile["temp_amp"] * sun_curve
            - (profile["break_cooling"] * 1.8) * break_curve
            + 0.25 * wobble
            + temp_delta
        )
        relative_humidity_percent = (
            profile["humidity_base"]
            - profile["humidity_amp"] * sun_curve
            + (profile["break_humidity_bump"] * 1.8) * break_curve
            + 1.2 * math.cos((2.0 * math.pi * progress) + profile["phase"] / 2.0)
            + humidity_delta
        )
        wind_speed_mps = (
            profile["wind_base"]
            - profile["wind_amp"] * sun_curve
            + (profile["break_wind_bump"] * 1.6) * break_curve
            + 0.15 * math.sin((4.0 * math.pi * progress) + profile["phase"])
            + wind_delta
        )

        relative_humidity_percent = _clamp(relative_humidity_percent, 30.0, 100.0)
        wind_speed_mps = max(0.2, wind_speed_mps)
        solar_load = profile["solar_load"] + (2.1 * sun_curve) - (1.6 * break_curve) + solar_delta
        wbgt_c = compute_wbgt(air_temperature_c, relative_humidity_percent, wind_speed_mps, solar_load)

        return air_temperature_c, relative_humidity_percent, wind_speed_mps, {
            "progress": progress,
            "break_curve": break_curve,
            "sun_curve": sun_curve,
            "solar_load": solar_load,
            "scenario": normalized_scenario,
            **scenario_metadata,
            **profile,
            "wbgt_c": wbgt_c,
        }

    def _build_reading(self, city: str, reading_at_utc: datetime, scenario: str = "baseline") -> WBGTReading:
        air_temperature_c, relative_humidity_percent, wind_speed_mps, metadata = self._simulate_environment(
            city,
            reading_at_utc,
            scenario=scenario,
        )
        wbgt_c = metadata["wbgt_c"]
        return WBGTReading(
            city=city,
            reading_at=reading_at_utc,
            air_temperature_c=air_temperature_c,
            relative_humidity_percent=relative_humidity_percent,
            wind_speed_mps=wind_speed_mps,
            wbgt_c=wbgt_c,
            source_name=self.source_name,
            source_url=self.source_url,
            metadata={
                "simulation_mode": True,
                "simulation_seed": self.seed,
                "simulation_profile": {
                    "scenario": metadata["scenario"],
                    "progress": metadata["progress"],
                    "break_curve": metadata["break_curve"],
                    "sun_curve": metadata["sun_curve"],
                    "solar_load": metadata["solar_load"],
                    "scenario_curve": metadata.get("scenario_curve", 0.0),
                },
            },
        )

    def get_reading(self, city: str, reading_at: datetime | None = None) -> WBGTReading:
        reading_at_utc = _ensure_aware(reading_at)
        return self._build_reading(city, reading_at_utc, scenario="baseline")

    def generate_workday_trace(
        self,
        city: str,
        reading_date: date | None = None,
        sample_count: int = 6,
        scenario: str = "baseline",
    ) -> list[WBGTReading]:
        reading_date = reading_date or datetime.now(timezone.utc).date()
        if sample_count < 2:
            raise ValueError("sample_count must be at least 2")
        normalized_scenario = _validate_wbgt_scenario(scenario)

        start_dt = datetime.combine(reading_date, self.workday_start, tzinfo=timezone.utc)
        end_dt = datetime.combine(reading_date, self.workday_end, tzinfo=timezone.utc)
        total_seconds = max(1.0, (end_dt - start_dt).total_seconds())
        step_seconds = total_seconds / float(sample_count - 1)

        return [
            self._build_reading(
                city,
                start_dt + timedelta(seconds=step_seconds * index),
                scenario=normalized_scenario,
            )
            for index in range(sample_count)
        ]


@dataclass(slots=True)
class WBGTRiskAgent:
    """Risk agent for simulated WBGT proxy readings and future sensor integrations.

    The default implementation emits simulated values, not live field data.
    """

    site_city: str | None = None
    reading_source: WBGTReadingSource | None = None
    reading_source_name: str | None = None
    reading_source_url: str | None = None
    min_consecutive_readings: int = 3
    elevated_threshold_c: float = WBGT_NORMAL_THRESHOLD_C
    max_history_minutes: int = 180
    _reading_history: dict[str, deque[WBGTReading]] = field(default_factory=lambda: defaultdict(deque), init=False, repr=False)

    def _resolve_city(self, city: str | None) -> str:
        resolved_city = (city or self.site_city or "").strip()
        if not resolved_city:
            raise ValueError("A site city must be provided to assess WBGT risk")
        return resolved_city

    def _resolve_reading_source(self) -> WBGTReadingSource:
        if self.reading_source is not None:
            return self.reading_source
        return SimulatedWBGTReadingSource()

    def _resolve_zone_key(self, city: str, zone_id: str | None = None) -> str:
        resolved_zone_id = (zone_id or city).strip()
        return resolved_zone_id or city

    def _track_and_filter(self, reading: WBGTReading, zone_key: str) -> bool:
        history = self._reading_history[zone_key]
        history.append(reading)

        cutoff = reading.reading_at - timedelta(minutes=self.max_history_minutes)
        while history and history[0].reading_at < cutoff:
            history.popleft()

        return _has_sustained_elevation(
            list(history),
            elevated_threshold_c=self.elevated_threshold_c,
            min_consecutive_readings=self.min_consecutive_readings,
        )

    def assess(
        self,
        city: str | None = None,
        reading_at: datetime | None = None,
        zone_id: str | None = None,
    ) -> WBGTRiskBatch:
        target_city = self._resolve_city(city)
        reading = self._resolve_reading_source().get_reading(target_city, reading_at)

        zone_key = self._resolve_zone_key(target_city, zone_id)
        sustained = self._track_and_filter(reading, zone_key)
        alert = classify_wbgt_risk(reading) if sustained else None

        return WBGTRiskBatch(
            site_city=reading.city,
            reading_at=reading.reading_at,
            wbgt_c=reading.wbgt_c,
            alerts=[alert] if alert is not None else [],
            reading_source_name=self.reading_source_name or reading.source_name,
            reading_source_url=self.reading_source_url or reading.source_url,
        )

    def assess_many(
        self,
        cities: list[str],
        reading_at: datetime | None = None,
    ) -> list[WBGTRiskBatch]:
        return [self.assess(city, reading_at) for city in cities]