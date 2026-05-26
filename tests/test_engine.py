import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("engine", ROOT / "fullspectrum_engine.py")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def settings(slot_count=4):
    colors = ["#FFFFFF", "#000000", "#D02040", "#2060C0"][:slot_count]
    matrix = []
    for row in range(slot_count):
        for column in range(slot_count):
            matrix.append("0" if row == column else "120")
    return {
        "filament_colour": colors,
        "filament_settings_id": ["Bambu PLA Basic @BBL H2C 0.2 nozzle"] * slot_count,
        "filament_ids": ["GFA00"] * slot_count,
        "filament_is_mixed": ["0"] * slot_count,
        "filament_mixed_components": [""] * slot_count,
        "filament_mixed_sublayer_ratios": [""] * slot_count,
        "filament_multi_colour": colors,
        "default_filament_colour": [""] * slot_count,
        "flush_volumes_matrix": matrix,
    }


def write_project(path):
    model = (
        '<?xml version="1.0"?><model><resources><object id="1"><mesh>'
        '<vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>'
        '<vertex x="0" y="1" z="0"/></vertices><triangles>'
        '<triangle v1="0" v2="1" v3="2" paint_color="8"/>'
        '</triangles></mesh></object></resources></model>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Metadata/project_settings.config", json.dumps(settings()))
        archive.writestr("3D/Objects/object_1.model", model)
        archive.writestr("Metadata/texture.png", b"unchanged-texture")

def write_bmp(path, color=(210, 180, 140)):
    red, green, blue = color
    row = bytes([blue, green, red, blue, green, red, 0, 0])
    data = row * 2
    header = b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, 2, 2, 1, 24, 0, len(data), 0, 0, 0, 0)
    path.write_bytes(header + dib + data)


class PaintCodecTests(unittest.TestCase):
    def test_known_bambu_leaf_states_are_slots_not_first_use_values(self):
        expected = {"8": 2, "0C": 3, "1C": 4, "DC": 16, "1FC": 19, "4FC": 22}
        for code, slot in expected.items():
            _, referenced = ENGINE.remap_paint_code(code, max_input_slot=32, max_output_slot=32)
            self.assertEqual(referenced, [slot], code)

    def test_codec_remaps_embedded_slot(self):
        mapped, referenced = ENGINE.remap_paint_code(
            "1C", slot_map={4: 2}, max_input_slot=4, max_output_slot=2
        )
        self.assertEqual(referenced, [4])
        self.assertEqual(mapped, "8")


class ArchiveSafetyTests(unittest.TestCase):
    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "unsafe.3mf"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "no")
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
                    ENGINE.safe_extract_archive(archive, Path(folder) / "extract")
            with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
                ENGINE.inspect_project(archive_path)

    def test_rejects_windows_style_traversal_and_duplicate_members(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "unsafe.3mf"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("Metadata\\..\\escape.txt", "no")
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
                    ENGINE.safe_extract_archive(archive, Path(folder) / "extract")
            duplicate = Path(folder) / "duplicate.3mf"
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("a.txt", "one")
                archive.writestr("A.TXT", "two")
            with zipfile.ZipFile(duplicate) as archive:
                with self.assertRaisesRegex(RuntimeError, "Duplicate path"):
                    ENGINE.safe_extract_archive(archive, Path(folder) / "extract2")


class ConversionTests(unittest.TestCase):
    def test_dynamic_physical_slots_and_preservation_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(
                source,
                "official",
                palette_source="catalog",
                real_slots="2",
                output_dir=folder,
                reveal=False,
            )
            self.assertEqual(output["realSlots"], 2)
            self.assertTrue(output["preservation"]["geometryPreserved"])
            self.assertTrue(output["preservation"]["textureResourcesPreserved"])
            with zipfile.ZipFile(output["output"]) as archive:
                generated = json.loads(archive.read("Metadata/project_settings.config"))
                total = output["outputSlots"]
                for key in [
                    "filament_colour",
                    "filament_settings_id",
                    "filament_ids",
                    "filament_is_mixed",
                    "filament_mixed_components",
                    "filament_mixed_sublayer_ratios",
                ]:
                    self.assertEqual(len(generated[key]), total, key)
                for index in range(2, total):
                    components = [int(value) for value in generated["filament_mixed_components"][index].split(",")]
                    self.assertTrue(all(component in (1, 2) for component in components))

    def test_conversion_is_deterministic_for_schema_and_paint(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            first_dir = Path(folder) / "first"
            second_dir = Path(folder) / "second"
            first = ENGINE.convert(source, "official", "catalog", first_dir, False, "3")
            second = ENGINE.convert(source, "official", "catalog", second_dir, False, "3")
            with zipfile.ZipFile(first["output"]) as a, zipfile.ZipFile(second["output"]) as b:
                self.assertEqual(
                    a.read("Metadata/project_settings.config"),
                    b.read("Metadata/project_settings.config"),
                )
                self.assertEqual(a.read("3D/Objects/object_1.model"), b.read("3D/Objects/object_1.model"))

    def test_reference_texture_adds_similarity_metric(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            reference = Path(folder) / "reference.bmp"
            write_project(source)
            write_bmp(reference)
            output = ENGINE.convert(
                source, "official", "catalog", folder, False, "3", reference=reference
            )
            self.assertEqual(output["reference"]["kind"], "Texture image")
            self.assertIn("referenceSimilarityScore", output["quality"])

    def test_validator_rejects_mixed_component_that_is_not_physical(self):
        obj = settings(3)
        obj["filament_is_mixed"] = ["0", "0", "1"]
        obj["filament_mixed_components"] = ["", "", "1,3"]
        obj["filament_mixed_sublayer_ratios"] = ["", "", "0.5000,0.5000"]
        with self.assertRaisesRegex(RuntimeError, "non-real|itself"):
            ENGINE.validate_arrays(obj, 3, 2, {}, None)

    def test_validator_rejects_zero_off_diagonal_purge_volume(self):
        obj = settings(2)
        obj["flush_volumes_matrix"] = ["0", "0", "120", "0"]
        with self.assertRaisesRegex(RuntimeError, "zero off-diagonal"):
            ENGINE.validate_arrays(obj, 2, 2, {"flush_volumes_matrix": ("matrix", 1)}, None)

    def test_predicted_preview_uses_mixed_color_estimate(self):
        obj = settings(3)
        obj["filament_is_mixed"] = ["0", "0", "1"]
        obj["filament_mixed_components"] = ["", "", "1,2"]
        obj["filament_mixed_sublayer_ratios"] = ["", "", "0.5000,0.5000"]
        predicted = ENGINE.preview_colors_from_project(obj)
        self.assertEqual(predicted[2], ENGINE.mix(["#FFFFFF", "#000000"], [0.5, 0.5]))

    def test_custom_palette_ignores_invalid_optional_quantity(self):
        with tempfile.TemporaryDirectory() as folder:
            palette = Path(folder) / "filaments.json"
            palette.write_text(json.dumps([
                {"name": "A", "color": "#FFFFFF", "remainingGrams": "unknown"},
                {"name": "B", "color": "#000000", "remainingGrams": 500},
            ]))
            choices = ENGINE.custom_palette(palette)
            self.assertIsNone(choices[0]["remainingGrams"])
            self.assertEqual(choices[1]["remainingGrams"], 500.0)


if __name__ == "__main__":
    unittest.main()
