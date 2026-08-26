from __future__ import annotations

"""Export deterministic simulated WBGT traces for heat-scenario testing.

SIMULATED OUTPUT ONLY: this script writes synthetic WBGT proxy traces for
workflow/testing use. The generated files are not real thermal camera or
physical WBGT sensor measurements.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.heat_detection.wbgt_risk import SimulatedWBGTReadingSource

SCENARIOS = [
    "baseline",
    "direct_sun_accumulation",
    "brief_spike",
    "fatigue_partial_recovery",
]

FIXED_SEED = 42
DEFAULT_CITY = "Shenzhen"
DEFAULT_SAMPLE_COUNT = 37
DEFAULT_READING_DATE = datetime(2026, 8, 10, tzinfo=timezone.utc).date()


def _resolve_output_dir() -> Path:
    output_dir = REPO_ROOT / "data" / "heat_proxy_or_synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _build_export_payload(
    scenario: str, readings: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "metadata": {
            "simulated_data": True,
            "note": (
                "SIMULATED OUTPUT ONLY: synthetic WBGT proxy trace for testing/workflow design. "
                "Not real thermal-camera or physical sensor output."
            ),
            "scenario": scenario,
            "seed": FIXED_SEED,
            "city": DEFAULT_CITY,
            "sample_count": DEFAULT_SAMPLE_COUNT,
            "reading_date": DEFAULT_READING_DATE.isoformat(),
        },
        "readings": readings,
    }


def main() -> None:
    source = SimulatedWBGTReadingSource(seed=FIXED_SEED)
    output_dir = _resolve_output_dir()

    for scenario in SCENARIOS:
        trace = source.generate_workday_trace(
            city=DEFAULT_CITY,
            reading_date=DEFAULT_READING_DATE,
            sample_count=DEFAULT_SAMPLE_COUNT,
            scenario=scenario,
        )
        payload = _build_export_payload(
            scenario, [reading.to_dict() for reading in trace]
        )

        output_path = output_dir / f"{scenario}.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {len(trace)} simulated readings to {output_path}")


if __name__ == "__main__":
    main()
