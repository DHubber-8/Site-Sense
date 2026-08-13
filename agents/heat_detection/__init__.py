"""Heat compliance alert agent package."""

from .agent import (
    HeatComplianceAlertAgent,
    OpenMeteoForecastClient,
    OpenWeatherForecastClient,
    WeatherForecastReading,
    classify_heat_alert,
)
from .schema import HeatComplianceAlert, HeatComplianceAlertBatch, WBGTRiskAlert, WBGTRiskBatch
from .wbgt_risk import (
    DEFAULT_SIMULATED_SOURCE_NAME,
    DEFAULT_SIMULATED_SOURCE_URL,
    WBGTRiskAgent,
    WBGTReading,
    WBGTReadingSource,
    SimulatedWBGTReadingSource,
    classify_wbgt_risk,
    compute_wbgt,
)

__all__ = [
    "HeatComplianceAlert",
    "HeatComplianceAlertAgent",
    "HeatComplianceAlertBatch",
    "WBGTRiskAlert",
    "WBGTRiskBatch",
    "WBGTRiskAgent",
    "WBGTReading",
    "WBGTReadingSource",
    "SimulatedWBGTReadingSource",
    "DEFAULT_SIMULATED_SOURCE_NAME",
    "DEFAULT_SIMULATED_SOURCE_URL",
    "OpenMeteoForecastClient",
    "OpenWeatherForecastClient",
    "WeatherForecastReading",
    "classify_heat_alert",
    "classify_wbgt_risk",
    "compute_wbgt",
]