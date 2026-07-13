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
        self.assertIn("1: Black (#000000)", summary)
        self.assertIn("Warning: One source color", summary)


if __name__ == "__main__":
    unittest.main()
