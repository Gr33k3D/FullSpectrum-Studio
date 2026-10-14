"""Regression coverage for Windows custom palettes and explicit Save Settings."""
import json
import tempfile
import unittest
from pathlib import Path

import fullspectrum_engine as engine
from desktop.filament_options import selectable_filament_options
from desktop.settings_store import load_settings, save_settings, validated_settings


class CustomFilamentSelectorTests(unittest.TestCase):
    def create_palette(self, directory, filaments):
        path = directory / "bundle.json"
        path.write_text(json.dumps({"filaments": filaments}), encoding="utf-8")
        return path

    def test_custom_palette_can_populate_color_chooser_without_bambu_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.create_palette(Path(td), [
                {"name": "Translucent Cyan", "brand": "Polymaker", "series": "Panchroma Translucent PLA", "color": "#08ABFB"},
                {"name": "Translucent Magenta", "brand": "Polymaker", "series": "Panchroma Translucent PLA", "color": "#D93B90"},
                {"name": "Translucent Yellow", "brand": "Polymaker", "series": "Panchroma Translucent PLA", "color": "#F9ED3D"},
                {"name": "Translucent Grey", "brand": "Polymaker", "series": "Panchroma Translucent PLA", "color": "#9199A4"},
            ])
            options = selectable_filament_options(engine, "custom", None, str(path))
            self.assertEqual(len(options), 4)
            self.assertEqual({v["color"] for v in options}, {"#08ABFB", "#D93B90", "#F9ED3D", "#9199A4"})
            self.assertTrue(all(v["key"].startswith("Panchroma Translucent PLA|") for v in options))

    def test_duplicate_custom_entries_share_single_selector_key(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.create_palette(Path(td), [
                {"name": "Cyan", "series": "PLA Basic", "color": "#0086D6"},
                {"name": "Duplicate Cyan", "series": "PLA Basic", "color": "#0086D6"},
                {"name": "White", "series": "PLA Basic", "color": "#FFFFFF"},
            ])
            options = selectable_filament_options(engine, "custom", None, str(path))
            self.assertEqual(len(options), 2)

    def test_custom_palette_errors_are_not_silently_replaced_with_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "invalid.json"
            path.write_text('{"filaments": !!!}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                selectable_filament_options(engine, "custom", None, str(path))
        self.assertEqual(selectable_filament_options(engine, "custom", None, ""), [])

    def test_bambu_selector_behavior_remains_unchanged(self):
        self.assertEqual(selectable_filament_options(engine, "inventory", None), [])
        options = [
            {"key": "PLA Basic|#FFFFFF", "name": "White", "series": "PLA Basic", "color": "#FFFFFF"},
            {"key": "PLA Matte|#FF0000", "name": "Red", "series": "PLA Matte", "color": "#FF0000"},
            {"key": "PLA Glow|#00FF00", "name": "Glow Green", "series": "PLA Glow", "color": "#00FF00"},
        ]
        snapshot = {"anchorOptions": options}
        self.assertEqual(len(selectable_filament_options(engine, "catalog", snapshot)), 2)
        self.assertEqual(len(selectable_filament_options(engine, "all-bambu", snapshot)), 3)
        self.assertEqual(selectable_filament_options(engine, "exact-cmykw", snapshot), [])


class DesktopSettingsTests(unittest.TestCase):
    def test_roundtrip_remembers_custom_path_source_and_palette_choices(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prefs" / "settings.json"
            original = {
                "custom": r"C:\Filament Libraries\Panchroma CMYG.json",
                "source": "custom", "real_slots": "4", "strategy": "official",
                "planner_mode": "best", "planning_sample": "preview", "catalog_region": "global",
                "quality_bias": 70, "smart_quality": False, "auto_preview": True,
                "auto_open": True, "output_application": "OrcaSlicer", "mix_model": "bambu",
                "disabled_anchor_keys": ["PLA Basic|#000000"],
                "pinned_anchor_keys": ["Panchroma Translucent PLA|#08ABFB"],
                "project": r"C:\Private Models\test.3mf",  # intentionally not persisted
            }
            save_settings(original, path)
            actual = load_settings(path)
            self.assertEqual(actual["source"], "custom")
            self.assertEqual(actual["custom"], original["custom"])
            self.assertEqual(actual["real_slots"], "4")
            self.assertEqual(actual["pinned_anchor_keys"], original["pinned_anchor_keys"])
            self.assertNotIn("project", actual)
            self.assertNotIn("Private Models", path.read_text(encoding="utf-8"))

    def test_missing_and_corrupted_settings_do_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            self.assertEqual(load_settings(path), {})
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(load_settings(path), {})
            path.write_text('{"version": 99, "source": "custom"}', encoding="utf-8")
            self.assertEqual(load_settings(path), {})

    def test_validation_rejects_unexpected_values(self):
        actual = validated_settings({
            "version": 1, "source": "arbitrary", "real_slots": "16",
            "quality_bias": True, "smart_quality": 1,
            "pinned_anchor_keys": ["ok", "ok", "other"],
            "disabled_anchor_keys": [123], "mysterious": "discard me",
        })
        self.assertEqual(actual, {"pinned_anchor_keys": ["ok", "other"]})

    def test_atomic_replace_preserves_existing_file_on_serialization_failure(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            save_settings({"source": "custom"}, path)
            save_settings({"source": "catalog"}, path)
            self.assertEqual(load_settings(path)["source"], "catalog")
            self.assertFalse(list(Path(td).glob(".settings-*.tmp")))


if __name__ == "__main__":
    unittest.main()
