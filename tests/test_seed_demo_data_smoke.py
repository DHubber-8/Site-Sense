"""Smoke tests for scripts/seed_demo_data.py's data-generation helpers."""

from __future__ import annotations

import unittest

from scripts.seed_demo_data import SAMPLE_IMAGES, _build_wbgt_assessments


class SeedDemoDataSmokeTest(unittest.TestCase):
    def test_seed_sample_images_include_the_real_image_set(self) -> None:
        """The seeding script should evaluate the full sample corpus instead of a tiny
        hardcoded subset; this keeps the demo database representative of the real model
        output across the repository's sample frames."""
        self.assertGreater(len(SAMPLE_IMAGES), 4)
        self.assertTrue(all(path.exists() for path in SAMPLE_IMAGES))

    def test_brief_spike_scenario_produces_no_wbgt_alert(self) -> None:
        """data/heat_proxy_or_synthetic/brief_spike.json is a single transient WBGT spike
        (wbgt_c=29.81 at 13:00, surrounded by readings below the elevated threshold) that
        must not alert once routed through the real sustained-elevation filter — the same
        fixture and expectation used by test_wbgt_risk_smoke.py and
        test_end_to_end_smoke.py via WBGTRiskAgent directly. The spike's exact reading value
        (unique to this scenario's synthetic curve) identifies it among the mixed-scenario
        output of _build_wbgt_assessments()."""
        assessments = _build_wbgt_assessments()

        brief_spike_alerts = [
            assessment
            for assessment in assessments
            if assessment.source == "heat_wbgt"
            and abs(assessment.source_detail.get("wbgt_c", 0.0) - 29.81056977436095)
            < 1e-6
        ]

        self.assertEqual(brief_spike_alerts, [])


if __name__ == "__main__":
    unittest.main()
