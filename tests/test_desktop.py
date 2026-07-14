import unittest
from pathlib import Path

from desktop import app_support
import fullspectrum_engine as engine

ROOT = Path(__file__).resolve().parents[1]


class WindowsDesktopTests(unittest.TestCase):
    def test_release_version_matches_shared_version_file(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(app_support.APP_VERSION, version)
        self.assertEqual(engine.APP_VERSION, version)
        self.assertEqual(engine.OUTPUT_VERSION, f"v{version}")

    def test_plan_preview_summary_is_non_writing_and_actionable(self):
        result = {
            "realSlots": 3,
            "outputSlots": 7,
            "anchors": [
                {"slot": 1, "name": "Black", "color": "#000000"},
                {"slot": 2, "name": "White", "color": "#FFFFFF"},
            ],
            "quality": {
                "qualityScore": 88.5,
                "estimatedDeltaE": 4.2,
                "maximumDeltaE": 8.4,
                "confidenceScore": 82.0,
            },
            "printability": {
                "paintedMixedShare": 31.0,
                "difficulty": "Moderate",
                "recommendations": ["Slice before estimating material."],
            },
            "warnings": ["One source color uses its nearest physical anchor."],
        }

        summary = app_support.format_plan_preview(result)

        self.assertIn("No 3MF was written", summary)
        self.assertIn("Physical slots: 3   Mixed slots: 4", summary)
        self.assertIn("Max dE: 8.40", summary)
        self.assertIn("1: Black (#000000)", summary)
        self.assertIn("Warning: One source color", summary)

    def test_shareable_error_report_excludes_private_diagnostics(self):
        report = app_support.format_shareable_error_report(
            "Could not convert C:\\Users\\Example\\Private Model.3mf; "
            'inventory={"spools":[{"remainingGrams":123}]}',
            log_created=True,
        )

        self.assertNotIn("Private Model", report)
        self.assertNotIn("remainingGrams", report)
        self.assertNotIn("C:\\Users", report)
        self.assertIn("private local log", report)
        self.assertIn("were excluded", report)

        ordinary_report = app_support.format_shareable_error_report(
            "A privately named object could not be decoded."
        )
        self.assertNotIn("privately named object", ordinary_report.lower())

    def test_live_forecast_exposes_accuracy_palette_and_inventory_gap(self):
        result = {
            "realSlots": 4,
            "outputSlots": 6,
            "outputColors": ["#FFFFFF", "#0047BB", "#FF9016", "#9D2235", "#14676D", "#847D48"],
            "quality": {
                "qualityScore": 61.4,
                "confidenceScore": 72.0,
                "maximumDeltaE": 31.2,
            },
            "worstMatch": {
                "targetColor": "#000000",
                "predictedColor": "#0047BB",
                "deltaE": 31.2,
                "suggestedFilament": {
                    "name": "PLA Basic Black",
                    "availability": "not in My Inventory",
                },
            },
        }

        forecast = app_support.plan_forecast(result)

        self.assertEqual(forecast["accuracy"], 61.4)
        self.assertEqual(forecast["slotSummary"], "4 physical + 2 mixed")
        self.assertEqual(forecast["colors"][1], "#0047BB")
        self.assertIn("Missing from My Inventory: PLA Basic Black", forecast["gapMessage"])


if __name__ == "__main__":
    unittest.main()
