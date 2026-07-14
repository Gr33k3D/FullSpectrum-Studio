import importlib.util
import json
import subprocess
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("engine", ROOT / "fullspectrum_engine.py")
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def settings(slot_count=4, preset="Bambu PLA Basic @BBL H2C 0.2 nozzle"):
    colors = ["#FFFFFF", "#000000", "#D02040", "#2060C0"][:slot_count]
    matrix = []
    for row in range(slot_count):
        for column in range(slot_count):
            matrix.append("0" if row == column else "120")
    return {
        "filament_colour": colors,
        "filament_settings_id": [preset] * slot_count,
        "filament_ids": ["GFA00"] * slot_count,
        "filament_is_mixed": ["0"] * slot_count,
        "filament_mixed_components": [""] * slot_count,
        "filament_mixed_sublayer_ratios": [""] * slot_count,
        "filament_multi_colour": colors,
        "default_filament_colour": [""] * slot_count,
        "flush_volumes_matrix": matrix,
    }


def write_project(path, project_settings=None):
    model = (
        '<?xml version="1.0"?><model><resources><object id="1"><mesh>'
        '<vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>'
        '<vertex x="0" y="1" z="0"/></vertices><triangles>'
        '<triangle v1="0" v2="1" v3="2" paint_color="8"/>'
        '</triangles></mesh></object></resources></model>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Metadata/project_settings.config", json.dumps(project_settings or settings()))
        archive.writestr("3D/Objects/object_1.model", model)
        archive.writestr("Metadata/texture.png", b"unchanged-texture")

def write_bmp(path, color=(210, 180, 140)):
    red, green, blue = color
    row = bytes([blue, green, red, blue, green, red, 0, 0])
    data = row * 2
    header = b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, 2, 2, 1, 24, 0, len(data), 0, 0, 0, 0)
    path.write_bytes(header + dib + data)

def write_png(path, pixels, width, height):
    raw=b"".join(b"\x00"+b"".join(bytes((*pixel,255)) for pixel in pixels[row*width:(row+1)*width])
                 for row in range(height))
    def chunk(kind, data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        +chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,6,0,0,0))
        +chunk(b"IDAT",zlib.compress(raw))
        +chunk(b"IEND",b"")
    )

def write_textured_obj(folder):
    texture=folder/"texture.png"
    write_png(texture,[(235,30,45),(25,100,230),(240,200,30),(35,185,90)],2,2)
    (folder/"sample.mtl").write_text("newmtl paint\nmap_Kd texture.png\n")
    model=folder/"sample.obj"
    model.write_text(
        "mtllib sample.mtl\n"
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "usemtl paint\nf 1/1 2/2 3/3\nf 1/1 3/3 4/4\n"
    )
    return model

def write_textured_glb(folder):
    texture=folder/"embedded.png"
    write_png(texture,[(210,40,45),(210,40,45),(210,40,45),(210,40,45)],2,2)
    image=texture.read_bytes()
    positions=struct.pack("<9f",0,0,0,1,0,0,0,1,0)
    uvs=struct.pack("<6f",0,0,1,0,0,1)
    indices=struct.pack("<3H",0,1,2)
    padding=b"\0\0"
    binary=positions+uvs+indices+padding+image
    document={
        "asset":{"version":"2.0"},
        "scene":0,
        "scenes":[{"nodes":[0]}],
        "nodes":[{"mesh":0,"translation":[2,0,0]}],
        "meshes":[{"primitives":[{"attributes":{"POSITION":0,"TEXCOORD_0":1},"indices":2}]}],
        "accessors":[
            {"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"},
            {"bufferView":1,"componentType":5126,"count":3,"type":"VEC2"},
            {"bufferView":2,"componentType":5123,"count":3,"type":"SCALAR"},
        ],
        "bufferViews":[
            {"buffer":0,"byteOffset":0,"byteLength":len(positions)},
            {"buffer":0,"byteOffset":len(positions),"byteLength":len(uvs)},
            {"buffer":0,"byteOffset":len(positions)+len(uvs),"byteLength":len(indices)},
            {"buffer":0,"byteOffset":len(positions)+len(uvs)+len(indices)+len(padding),"byteLength":len(image)},
        ],
        "images":[{"bufferView":3,"mimeType":"image/png"}],
        "buffers":[{"byteLength":len(binary)}],
    }
    encoded=json.dumps(document,separators=(",",":")).encode()
    encoded+=b" " * ((4-len(encoded)%4)%4)
    binary+=b"\0" * ((4-len(binary)%4)%4)
    total=12+8+len(encoded)+8+len(binary)
    glb=folder/"sample.glb"
    glb.write_bytes(b"glTF"+struct.pack("<II",2,total)+struct.pack("<II",len(encoded),0x4E4F534A)+encoded+struct.pack("<II",len(binary),0x004E4942)+binary)
    return glb


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

    def test_eight_digit_color_preserves_32_slot_paint_reference(self):
        colors = ["#00000000"] + [f"#{slot:06X}" for slot in range(1, 32)]
        parsed = ENGINE.colors_from_project({"filament_colour": colors})

        self.assertEqual(len(parsed), 32)
        self.assertEqual(parsed[0], "#000000")
        self.assertEqual(parsed[-1], "#00001F")
        self.assertEqual(ENGINE.paint_slot_usage({"EFC": 2}, len(parsed)), {32: 2})

    def test_invalid_project_color_reports_slot_instead_of_shifting_palette(self):
        with self.assertRaisesRegex(RuntimeError, "filament_colour slot 2"):
            ENGINE.colors_from_project({"filament_colour": ["#FFFFFF", "not-a-color", "#000000"]})

    def test_ciede2000_uses_standard_reference_pair(self):
        difference = ENGINE.delta_e_2000((50, 2.6772, -79.7751), (50, 0, -82.7485))
        self.assertAlmostEqual(difference, 2.0425, places=3)


class BambuColorModelTests(unittest.TestCase):
    def test_bambu_reconstruction_color_regressions(self):
        cases = {
            "purple": (["#EC008C", "#0A2E8A"], "#6E0D92"),
            "green": (["#00AEEF", "#F4EE2A"], "#5EE569"),
            "orange": (["#C12E1F", "#F4EE2A"], "#E27B34"),
            "neutral": (["#000000", "#FFFFFF"], "#647DA0"),
            "dark": (["#042F56", "#482960"], "#222C61"),
        }
        for name, (colors, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(ENGINE.mix(colors, [0.5, 0.5]), expected)

    def test_preview_reconstructs_bambu_loaded_angel_swatches(self):
        physical = ["#F7E6DE", "#042F56", "#7D6556", "#E8DBB7", "#BA9594", "#F7D959"]
        expected = ["#CFB9AC", "#D5BA72", "#BBA496", "#A08D59", "#E0C569", "#B3A05A",
                    "#9C8574", "#2C587C", "#578FA1", "#978358", "#496986", "#16405D",
                    "#5D95B6", "#2C746A", "#96B8B1", "#50926A", "#3677A0", "#236488"]
        components = ["1,3", "5,6", "1,3", "3,6", "5,6", "3,6", "1,3", "2,5", "2,4",
                      "3,6", "2,5", "2,3", "1,2", "2,6", "2,4", "2,6", "1,2", "2,4"]
        ratios = ["0.6667,0.3333", "0.5000,0.5000", "0.5000,0.5000", "0.6667,0.3333",
                  "0.3333,0.6667", "0.5000,0.5000", "0.2500,0.7500", "0.6667,0.3333",
                  "0.5000,0.5000", "0.7500,0.2500", "0.5000,0.5000", "0.7500,0.2500",
                  "0.5000,0.5000", "0.6667,0.3333", "0.2500,0.7500", "0.5000,0.5000",
                  "0.3333,0.6667", "0.7500,0.2500"]
        obj = settings(24)
        obj["filament_colour"] = physical + ["#000000"] * len(expected)
        obj["filament_multi_colour"] = obj["filament_colour"][:]
        obj["filament_is_mixed"] = ["0"] * 6 + ["1"] * len(expected)
        obj["filament_mixed_components"] = [""] * 6 + components
        obj["filament_mixed_sublayer_ratios"] = [""] * 6 + ratios
        self.assertEqual(ENGINE.preview_colors_from_project(obj)[6:], expected)


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

    def test_glb_declared_oversize_rejects_before_geometry_decode(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder=Path(folder_name)
            source=write_textured_glb(folder)
            data=source.read_bytes()
            json_length=struct.unpack_from("<I",data,12)[0]
            document=json.loads(data[20:20+json_length].decode("utf-8"))
            document["accessors"][2]["count"]=(ENGINE.MAX_IMPORT_FACES+1)*3
            encoded=json.dumps(document,separators=(",",":")).encode()
            encoded+=b" " * ((4-len(encoded)%4)%4)
            bin_header=20+json_length
            old_binary_length=struct.unpack_from("<I",data,bin_header)[0]
            binary=data[bin_header+8:bin_header+8+old_binary_length]
            total=12+8+len(encoded)+8+len(binary)
            oversized=folder/"oversized.glb"
            oversized.write_bytes(
                b"glTF"+struct.pack("<II",2,total)
                +struct.pack("<II",len(encoded),0x4E4F534A)+encoded
                +struct.pack("<II",len(binary),0x004E4942)+binary
            )
            with self.assertRaisesRegex(RuntimeError,"face import safety limit"):
                ENGINE.import_glb_project(oversized,folder/"out.3mf",folder)


class ErrorReportingTests(unittest.TestCase):
    def test_custom_palette_json_errors_include_line_and_column(self):
        with tempfile.TemporaryDirectory() as folder:
            palette = Path(folder) / "bad.json"
            palette.write_text("{ bad")
            with self.assertRaisesRegex(RuntimeError, "line 1, column 3"):
                ENGINE.custom_palette(palette)

    def test_cli_error_includes_traceback_not_none(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.3mf"
            bad.write_text("not a zip")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "fullspectrum_engine.py"),
                    "--json",
                    "--inspect",
                    str(bad),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("ERROR:", completed.stderr)
            self.assertIn("Traceback", completed.stderr)
            self.assertNotEqual(completed.stderr.strip().lower(), "none")


class ConversionTests(unittest.TestCase):
    def test_binary_paint_remap_preserves_nonpaint_model_bytes(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            objects = folder / "3D" / "Objects"
            objects.mkdir(parents=True)
            source = (
                b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
                b'<model><resources><object id="1"><mesh>\r\n'
                b'<vertices><vertex x="0" y="0" z="0"/></vertices>\r\n'
                b'<triangles><triangle v1="0" v2="0" v3="0" paint_color="8"/></triangles>\r\n'
                b'</mesh></object></resources></model>\r\n'
            )
            model = objects / "object_1.model"
            model.write_bytes(source)
            mapped, _ = ENGINE.remap_paint_code("8", {2: 1}, 4, 2)

            patched = ENGINE.remap_paint_codes_by_codec(folder, {2: 1}, 4, 2)

            self.assertEqual(patched, ["3D/Objects/object_1.model"])
            self.assertEqual(
                model.read_bytes(),
                source.replace(b'paint_color="8"', f'paint_color="{mapped}"'.encode()),
            )

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
            self.assertTrue(output["preservation"]["paintRemapVerified"])
            self.assertIn("confidenceScore",output["quality"])
            self.assertIn("contrastRetention",output["quality"])
            self.assertTrue(output["colorValidation"]["verified"])
            self.assertEqual(output["colorValidation"]["maximumDeltaE"], 0.0)
            self.assertTrue(Path(output["colorValidationReport"]).exists())
            self.assertTrue(output["printability"]["sliceRequiredForTimeAndUsage"])
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

    def test_shareable_report_does_not_repeat_reference_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            reference = Path(folder) / "private-reference-name.bmp"
            palette = Path(folder) / "local-owned-filaments.json"
            write_project(source)
            write_bmp(reference)
            palette.write_text(json.dumps([
                {"name": "Owned White", "color": "#FFFFFF", "remainingGrams": 500},
                {"name": "Owned Black", "color": "#000000", "remainingGrams": 420},
            ]))
            output = ENGINE.convert(
                source, "official", "custom", folder, False, "2",
                reference=reference, custom_catalog_path=palette
            )
            report = Path(output["report"]).read_text()
            self.assertIn("Reference type: Texture image", report)
            self.assertNotIn(reference.name, report)
            self.assertNotIn("Available PLA inventory", report)
            self.assertNotIn(" g available", report)
            self.assertNotIn("500", report)
            self.assertNotIn("420", report)

    def test_analysis_meshes_are_emitted_for_loss_and_anchor_influence(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(source, "official", "catalog", folder, False, "2",
                                    analysis_dir=Path(folder)/"analysis")
            heatmap = Path(output["analysisAssets"]["heatmapMesh"])
            influence = Path(output["analysisAssets"]["anchorInfluenceMesh"])
            self.assertTrue(heatmap.exists())
            self.assertTrue(influence.exists())
            heat_geometry = "\n".join(line for line in heatmap.read_text().splitlines()
                                      if not line.startswith("mtllib "))
            influence_geometry = "\n".join(line for line in influence.read_text().splitlines()
                                           if not line.startswith("mtllib "))
            self.assertEqual(heat_geometry, influence_geometry)

    def test_plan_preview_uses_preview_weighting_without_writing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            with zipfile.ZipFile(source) as archive:
                self.assertEqual(ENGINE.preview_slot_usage(archive, 4), {2: 1})
            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "2",
                planner_mode="fast",
                planning_sample="preview",
                plan_only=True,
            )
            self.assertEqual(output["type"], "planPreview")
            self.assertEqual(output["planningSample"], "preview")
            self.assertEqual(output["realSlots"], 2)
            self.assertIn("quality", output)
            self.assertIn("recipes", output)
            self.assertTrue(any("preview-mesh color weighting" in warning for warning in output["warnings"]))
            generated = list(Path(folder).glob("*FullSpectrum*.3mf"))
            self.assertEqual(generated, [])

    def test_plan_preview_emits_live_predicted_mesh_without_writing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            analysis = Path(folder) / "live-forecast"
            write_project(source)

            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "2",
                planner_mode="fast",
                plan_only=True,
                analysis_dir=analysis,
            )

            self.assertEqual(output["type"], "planPreview")
            self.assertEqual(len(output["outputColors"]), output["outputSlots"])
            self.assertIsNotNone(output["worstMatch"])
            self.assertTrue(Path(output["analysisAssets"]["predictedMesh"]).exists())
            self.assertTrue(Path(output["analysisAssets"]["heatmapMesh"]).exists())
            self.assertTrue(Path(output["analysisAssets"]["anchorInfluenceMesh"]).exists())
            self.assertEqual(list(Path(folder).glob("*FullSpectrum*.3mf")), [])

    def test_metadata_only_inspection_avoids_mesh_scan_and_preview_build(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            preview = Path(folder) / "preview.obj"
            write_project(source)
            inspected = ENGINE.inspect_project(source, preview_mesh_dest=preview, metadata_only=True)
            self.assertIsNone(inspected["metrics"])
            self.assertIsNone(inspected["previewMesh"])
            self.assertFalse(preview.exists())

    def test_large_interactive_preview_uses_optimized_fallback_under_resource_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            preview = Path(folder) / "preview.obj"
            write_project(source)
            previous_limit = ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES
            try:
                ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES = 0
                inspected = ENGINE.inspect_project(source, preview_mesh_dest=preview)
            finally:
                ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES = previous_limit
            self.assertIsNotNone(inspected["previewMesh"])
            self.assertIn("Using optimized preview", inspected["previewNotice"])
            self.assertTrue(preview.exists())
            self.assertIn("s 1", preview.read_text())

    def test_large_analysis_overlays_use_optimized_fallback_under_resource_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            previous_limit = ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES
            try:
                ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES = 0
                output = ENGINE.convert(source, "official", "catalog", folder, False, "2",
                                        analysis_dir=Path(folder) / "analysis")
            finally:
                ENGINE.MAX_INTERACTIVE_PREVIEW_TRIANGLES = previous_limit
            self.assertTrue(Path(output["analysisAssets"]["heatmapMesh"]).exists())
            self.assertTrue(Path(output["analysisAssets"]["anchorInfluenceMesh"]).exists())
            self.assertTrue(Path(output["analysisAssets"]["predictedMesh"]).exists())
            self.assertTrue(any("Using optimized preview overlays" in warning for warning in output["warnings"]))
            self.assertTrue(output["preservation"]["paintRemapVerified"])

    def test_reuses_equal_mix_recipe_instead_of_creating_duplicate_slots(self):
        anchors=[
            {"name":"Black","color":"#000000"},
            {"name":"White","color":"#FFFFFF"},
        ]
        reconstructable=ENGINE.mix(["#000000","#FFFFFF"],[0.5,0.5])
        palette=ENGINE.build_palette([reconstructable,reconstructable],anchors,{1:100,2:100},100)
        self.assertEqual(len(palette[0]),3)
        self.assertEqual(palette[4][1],palette[4][2])

    def test_anchor_score_hint_database_reuses_bambu_mix_recipes(self):
        ENGINE.anchor_score_hint_database.cache_clear()
        target=ENGINE.mix(["#000000","#FFFFFF"],[0.5,0.5])
        hints=ENGINE.anchor_score_hint_database(
            ("#000000","#FFFFFF","#FF0000"),
            (target,),
            "bambu",
            "fine2",
            "standard3",
            14.0,
        )
        self.assertTrue(
            any(set(components)=={"#000000","#FFFFFF"} and error < 0.1
                for components,error in hints[0])
        )
        before=ENGINE.anchor_score_hint_database.cache_info()
        ENGINE.anchor_score_hint_database(
            ("#000000","#FFFFFF","#FF0000"),
            (target,),
            "bambu",
            "fine2",
            "standard3",
            14.0,
        )
        after=ENGINE.anchor_score_hint_database.cache_info()
        self.assertEqual(after.hits,before.hits+1)

    def test_quality_mix_limit_is_conservative_until_quality_is_raised(self):
        self.assertEqual(ENGINE.quality_mix_limit(60),ENGINE.MAX_RELIABLE_MIX_DE)
        self.assertEqual(ENGINE.quality_mix_limit(100),ENGINE.MAX_HIGH_QUALITY_MIX_DE)

    def test_best_planner_searches_denser_mix_ratios_than_fast(self):
        anchors=[
            {"name":"Black","color":"#000000"},
            {"name":"White","color":"#FFFFFF"},
        ]
        target=ENGINE.mix(["#000000","#FFFFFF"],[0.2,0.8])
        fast=ENGINE.build_palette([target],anchors,{1:100},100,planner_mode="fast")[-1][0]
        best=ENGINE.build_palette([target],anchors,{1:100},100,planner_mode="best")[-1][0]
        self.assertLessEqual(float(best[8]),float(fast[8]))

    def test_auto_planner_preserves_small_black_and_white_details(self):
        with tempfile.TemporaryDirectory() as folder_name:
            palette = Path(folder_name) / "palette.json"
            candidates = [
                {"name": name, "color": color}
                for name, color in ENGINE.BAMBU_PLA
            ] + [
                {"name": "Pumpkin", "color": "#FF9016"},
                {"name": "Maroon", "color": "#9D2235"},
                {"name": "Mistletoe", "color": "#3F8E43"},
                {"name": "Current Dark Blue", "color": "#042F56"},
                {"name": "Current Lemon", "color": "#F7D959"},
            ]
            palette.write_text(json.dumps(candidates))
            old_colors = ["#FFFFFF", "#000000", "#FF9016", "#14676D", "#9D2235"]
            usage = {1: 8320, 2: 2912, 3: 86768, 4: 120656, 5: 25536}

            anchors = ENGINE.select_anchors(
                old_colors,
                usage,
                "official",
                {"spools": []},
                "custom",
                "auto",
                custom_catalog_path=palette,
                quality_bias=60,
            )
            rows = ENGINE.build_palette(old_colors, anchors, usage, 60)[-1]
            metrics = ENGINE.quality_metrics(rows, usage, old_colors)
            selected = {ENGINE.anchor_color(anchor) for anchor in anchors}

            self.assertIn("#000000", selected)
            self.assertIn("#FFFFFF", selected)
            self.assertEqual(len(anchors), len(old_colors))
            self.assertLess(metrics["maximumDeltaE"], 8.0)

    def test_quality_score_is_capped_by_worst_visible_error(self):
        rows = [
            [1, 1, "#000000", "ANCHOR", "Black", "", "", "#000000", "0.00", "0.00", "0.00"],
            [2, 1, "#FFFFFF", "ANCHOR", "Black", "", "", "#000000", "30.00", "30.00", "0.00"],
        ]
        metrics = ENGINE.quality_metrics(rows, {1: 1000, 2: 1}, ["#000000", "#FFFFFF"])

        self.assertEqual(metrics["maximumDeltaE"], 30.0)
        self.assertLessEqual(metrics["qualityScore"], 64.0)

    def test_inventory_gap_recommends_a_missing_black_filament(self):
        inventory = {
            "spools": [
                {
                    "name": "Owned Blue",
                    "series": "PLA Basic",
                    "brand": "Bambu Lab",
                    "color": "#0047BB",
                    "preset": "Bambu PLA Basic",
                    "filamentID": "GFA00",
                    "remainingGrams": 500.0,
                    "initialGrams": 1000.0,
                },
                {
                    "name": "Owned White",
                    "series": "PLA Basic",
                    "brand": "Bambu Lab",
                    "color": "#FFFFFF",
                    "preset": "Bambu PLA Basic",
                    "filamentID": "GFA00",
                    "remainingGrams": 500.0,
                    "initialGrams": 1000.0,
                },
            ]
        }
        rows = [
            [1, 1, "#000000", "ANCHOR", "Owned Blue", "", "", "#0047BB", "35.0", "35.0", "0.0"],
        ]

        match = ENGINE.worst_color_match(rows, {1: 10}, "inventory", inventory)

        self.assertEqual(match["targetColor"], "#000000")
        self.assertEqual(match["severity"], "poor")
        self.assertIsNotNone(match["suggestedFilament"])
        self.assertIn("black", match["suggestedFilament"]["name"].lower())
        self.assertEqual(match["suggestedFilament"]["availability"], "not in My Inventory")

    def test_unused_source_color_does_not_create_an_unused_mix_slot(self):
        anchors = [
            {"name": "Black", "color": "#000000"},
            {"name": "White", "color": "#FFFFFF"},
        ]
        used = ENGINE.mix(["#000000", "#FFFFFF"], [0.5, 0.5])
        unused = ENGINE.mix(["#000000", "#FFFFFF"], [0.25, 0.75])

        palette = ENGINE.build_palette([used, unused], anchors, {1: 100, 2: 0}, 100)

        self.assertEqual(len(palette[0]), 3)
        self.assertEqual(palette[-1][0][3], "MIX")
        self.assertEqual(palette[-1][1][3], "ANCHOR")

    def test_smart_quality_bias_runs_multiple_plans_and_reports_selected_value(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "auto",
                quality_bias="auto",
                planner_mode="fast",
            )
            self.assertEqual(output["qualityBiasMode"], "auto")
            self.assertEqual(output["plannerMode"], "fast")
            self.assertIn(output["qualityBias"], ENGINE.SMART_QUALITY_CANDIDATES)
            self.assertEqual(output["quality"]["resolvedQualityBias"], output["qualityBias"])
            self.assertEqual(output["quality"]["plannerMode"], "fast")
            self.assertEqual(output["quality"]["smartSearchMode"], "adaptive-spectrum")
            self.assertGreaterEqual(len(output["quality"].get("smartCandidates", [])), 1)
            self.assertIn("skippedQualityCandidates", output["quality"])
            self.assertIn("Smart auto selected", Path(output["report"]).read_text())
            self.assertIn("Planner mode: Fast", Path(output["report"]).read_text())

    def test_catalog_region_is_visible_in_outputs_and_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "2",
                catalog_region="eu",
                planner_mode="fast",
            )
            self.assertEqual(output["catalogRegion"], "eu")
            self.assertEqual(output["catalogRegionLabel"], "Europe")
            self.assertTrue(any("Europe" in warning for warning in output["warnings"]))
            self.assertIn("Catalog planning region: Europe", Path(output["report"]).read_text())

    def test_unknown_catalog_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            with self.assertRaisesRegex(RuntimeError, "Unknown catalog region"):
                ENGINE.convert(
                    source,
                    "official",
                    "catalog",
                    folder,
                    False,
                    "2",
                    catalog_region="mars",
                )

    def test_official_strategy_allows_experimental_extra_physical_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "7",
                quality_bias=100,
                planner_mode="fast",
            )
            self.assertEqual(output["realSlots"], 7)
            self.assertEqual(output["validation"], "OK")
            self.assertTrue(any("Experimental 7-physical-slot" in warning for warning in output["warnings"]))

    def test_auto_real_slots_keeps_support_slot_available(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.3mf"
            write_project(source)
            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "auto",
                quality_bias=100,
                planner_mode="fast",
            )
            self.assertLessEqual(output["realSlots"], ENGINE.DEFAULT_AUTO_MAX_REAL_SLOTS)

    def test_conversion_rebinds_builtin_presets_to_source_printer(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            source = folder / "source.3mf"
            project_settings = settings(preset="Bambu PLA Basic @BBL A1")
            project_settings["printer_model"] = "Bambu Lab A1"
            project_settings["nozzle_diameter"] = ["0.4"]
            write_project(source, project_settings)

            output = ENGINE.convert(
                source,
                "official",
                "catalog",
                folder,
                False,
                "2",
                quality_bias=100,
                planner_mode="fast",
            )

            with zipfile.ZipFile(output["output"]) as archive:
                written = json.loads(archive.read("Metadata/project_settings.config"))
            presets = written["filament_settings_id"]
            self.assertEqual(len(presets), output["outputSlots"])
            self.assertTrue(all(preset.endswith("@BBL A1") for preset in presets))
            self.assertTrue(all("H2C" not in preset for preset in presets))

    def test_anchor_selection_keeps_mix_parent_colors_when_they_improve_output(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            palette = folder / "palette.json"
            palette.write_text(json.dumps([
                {"name": "Yellow", "color": "#F4EE2A"},
                {"name": "Ash Gray", "color": "#9B9B9B"},
                {"name": "Copper", "color": "#B87333"},
                {"name": "Dark Chocolate", "color": "#4D3324"},
                {"name": "White", "color": "#FFFFFF"},
                {"name": "Black", "color": "#000000"},
            ]))
            old_colors = ["#F4EE2A", "#AE835B", "#4D3324", "#A6A9AA"]
            usage = {1: 200, 2: 1400, 3: 900, 4: 500}
            anchors = ENGINE.select_anchors(
                old_colors,
                usage,
                "official",
                {"spools": []},
                "custom",
                "4",
                custom_catalog_path=palette,
                quality_bias=60,
            )
            colors = {anchor["color"] for anchor in anchors}
            self.assertIn("#B87333", colors)
            self.assertIn("#9B9B9B", colors)

    def test_rejects_misleading_mixed_recipe_even_when_it_beats_bad_anchors(self):
        anchors=[
            {"name":"Black","color":"#000000"},
            {"name":"Pink","color":"#BA9594"},
        ]
        palette=ENGINE.build_palette(["#335599"],anchors,{1:100},100,planner_mode="fast")
        self.assertEqual(len(palette[0]),2)
        self.assertEqual(palette[5][0][3],"ANCHOR")

    def test_quality_100_cmykw_keeps_warm_tones_from_collapsing_to_white(self):
        old_colors=[
            "#F7E6DE","#00AEEF","#EC008C","#F4EE2A","#000000","#FFFFFF",
            "#F5F0E8","#DBBA8A","#B59989","#CDB7AA","#938A62","#A7A482",
            "#95B5A7","#D19B4E","#937EA6",
        ]
        usage={
            1:731053,2:13494,3:1680,4:139745,5:5820,8:1634644,9:611411,
            10:1566760,11:13686,12:25059,13:35007,14:20104,15:17603,
        }
        new_colors,_,_,_,mapping,rows=ENGINE.build_palette(
            old_colors,ENGINE.exact_cmykw_palette(),usage,100
        )
        total=sum(usage.values())
        bright=sum(
            usage.get(old_slot,0)
            for old_slot,new_slot in mapping.items()
            if ENGINE.luminance(new_colors[new_slot-1])>210
        )
        self.assertLess(bright/total,0.35)
        for old_slot in (8,9,10):
            self.assertEqual(rows[old_slot-1][3],"MIX")
            self.assertNotEqual(new_colors[mapping[old_slot]-1],"#F5F0E8")

    def test_official_names_keep_multiword_family_and_known_catalog_color(self):
        self.assertEqual(ENGINE.filament_family("PLA Matte Desert Tan"),"PLA Matte")
        self.assertEqual(ENGINE.official_filament_name("PLA Matte","#E8DBB7"),"PLA Matte Desert Tan")
        self.assertEqual(ENGINE.official_filament_name("PLA Basic","#000000"),"PLA Basic Black")

    def test_catalog_palette_reads_bambu_studio_color_codes_when_available(self):
        source, rows = ENGINE.bambu_studio_catalog_rows()
        if not rows:
            self.skipTest("Bambu Studio catalog is not installed on this machine")
        palette = ENGINE.catalog_palette("core")
        by_name = {item["name"]: item for item in palette}
        self.assertIn("PLA Basic Cyan", by_name)
        self.assertEqual(by_name["PLA Basic Cyan"]["color"], "#0086D6")
        self.assertEqual(by_name["PLA Basic Cyan"]["filamentID"], "GFA00")
        self.assertEqual(by_name["PLA Basic Cyan"]["catalogSource"], source)
        self.assertNotIn("PLA Basic Arctic Whisper", by_name)

    def test_catalog_summary_reports_official_source_counts(self):
        summary = ENGINE.catalog_summary()
        self.assertIn("source", summary)
        self.assertGreater(summary["totalRows"], 0)
        self.assertGreater(summary["coreUsableCount"], 0)
        self.assertGreaterEqual(summary["allUsableCount"], summary["coreUsableCount"])
        self.assertTrue(any(item["series"] == "PLA Basic" for item in summary["families"]))

    def test_material_filter_and_pinned_anchor_constrain_selection(self):
        inventory = {
            "spools": [
                {
                    "name": "PLA Basic Black",
                    "series": "PLA Basic",
                    "brand": "Bambu Lab",
                    "color": "#000000",
                    "preset": "Bambu PLA Basic @BBL H2C 0.2 nozzle",
                    "filamentID": "GFA00",
                    "remainingGrams": 1000,
                    "initialGrams": 1000,
                },
                {
                    "name": "PLA Basic White",
                    "series": "PLA Basic",
                    "brand": "Bambu Lab",
                    "color": "#FFFFFF",
                    "preset": "Bambu PLA Basic @BBL H2C 0.2 nozzle",
                    "filamentID": "GFA00",
                    "remainingGrams": 1000,
                    "initialGrams": 1000,
                },
                {
                    "name": "PLA Matte Scarlet Red",
                    "series": "PLA Matte",
                    "brand": "Bambu Lab",
                    "color": "#D32941",
                    "preset": "Bambu PLA Matte @BBL H2C 0.2 nozzle",
                    "filamentID": "GFA01",
                    "remainingGrams": 1000,
                    "initialGrams": 1000,
                },
            ]
        }
        anchors = ENGINE.select_anchors(
            ["#111111", "#F7F7F7", "#D32941"],
            {1: 80, 2: 40, 3: 20},
            "official",
            inventory,
            "inventory",
            "2",
            material_families="PLA Basic",
            pinned_anchor_keys="PLA Basic|#000000",
        )
        self.assertEqual(ENGINE.anchor_key(anchors[0]), "PLA Basic|#000000")
        self.assertTrue(all(anchor["series"] == "PLA Basic" for anchor in anchors))

    def test_textured_obj_import_runs_through_validated_output(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder=Path(folder_name)
            source=write_textured_obj(folder)
            output=ENGINE.convert(source,"official","catalog",folder,False,"2",internal_colors=40)
            self.assertEqual(output["import"]["sourceType"],"Textured OBJ")
            self.assertTrue(output["preservation"]["paintRemapVerified"])
            with zipfile.ZipFile(output["output"]) as archive:
                self.assertIn("3D/Textures/source_texture.png",archive.namelist())
            preview=ENGINE.inspect_project(source,preview_mesh_dest=folder/"preview.obj")
            self.assertEqual(preview["filename"],"sample.obj")
            self.assertTrue(Path(preview["previewMesh"]).exists())

    def test_textured_glb_import_runs_through_validated_output(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder=Path(folder_name)
            source=write_textured_glb(folder)
            output=ENGINE.convert(source,"official","catalog",folder,False,"2")
            self.assertEqual(output["import"]["sourceType"],"Textured GLB")
            self.assertTrue(output["preservation"]["paintRemapVerified"])
            preview=ENGINE.inspect_project(source,preview_mesh_dest=folder/"glb-preview.obj")
            self.assertEqual(preview["filename"],"sample.glb")

    def test_texture_without_geometry_is_rejected_as_direct_input(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder=Path(folder_name)
            image=folder/"texture.png"
            write_png(image,[(0,0,0)],1,1)
            with self.assertRaisesRegex(RuntimeError,"no printable geometry"):
                ENGINE.convert(image,"official","catalog",folder,False,"2")

    def test_practical_bias_never_creates_more_mixes_than_detail_bias(self):
        anchors=[{"name":"Black","color":"#000000"},{"name":"White","color":"#FFFFFF"}]
        colors=["#303030","#606060","#909090","#C0C0C0"]
        practical=ENGINE.build_palette(colors,anchors,{i:100 for i in range(1,5)},0)
        detail=ENGINE.build_palette(colors,anchors,{i:100 for i in range(1,5)},100)
        self.assertLessEqual(len(practical[0]),len(detail[0]))

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

    def test_h2c_two_nozzle_arrays_resize_as_complete_slot_blocks(self):
        old_colors = ["#9D2235", "#042F56", "#F7D959", "#FF9016", "#000000", "#1D6569"]
        old_count = len(old_colors)
        matrix_block = [
            "0" if row == column else str(100 + row * old_count + column)
            for row in range(old_count)
            for column in range(old_count)
        ]
        obj = {
            "filament_colour": old_colors[:],
            "filament_self_index": [str(slot) for slot in range(1, old_count + 1) for _ in range(2)],
            "filament_retraction_length": [f"{slot}.{nozzle}" for slot in range(1, old_count + 1) for nozzle in range(2)],
            "flush_volumes_vector": [str(140 + index) for index in range(old_count * 2)],
            "flush_volumes_matrix": matrix_block + matrix_block,
        }
        layouts = ENGINE.filament_array_layouts(obj, old_count)
        representatives = [1, 2, 3, 4, 6]
        new_colors = [old_colors[index - 1] for index in representatives]

        ENGINE.resize_project_filament_arrays(
            obj, old_count, representatives, layouts, old_colors, new_colors
        )

        self.assertEqual(layouts["flush_volumes_matrix"], ("matrix", 2))
        self.assertEqual(layouts["flush_volumes_vector"], ("slot", 2))
        self.assertEqual(len(obj["flush_volumes_matrix"]), 2 * len(representatives) ** 2)
        self.assertEqual(len(obj["flush_volumes_vector"]), 2 * len(representatives))
        self.assertEqual(len(obj["filament_retraction_length"]), 2 * len(representatives))
        self.assertEqual(
            obj["filament_self_index"],
            [str(slot) for slot in range(1, len(representatives) + 1) for _ in range(2)],
        )

    def test_h2c_three_value_filament_arrays_grow_as_complete_slot_blocks(self):
        old_colors = ["#FFFFFF", "#000000", "#FF9016", "#14676D", "#9D2235"]
        old_count = len(old_colors)
        obj = {
            "filament_colour": old_colors[:],
            "filament_self_index": [
                str(slot) for slot in range(1, old_count + 1) for _ in range(3)
            ],
            "filament_flow_ratio": [
                f"{slot}.{variant}"
                for slot in range(1, old_count + 1)
                for variant in range(3)
            ],
        }
        layouts = ENGINE.filament_array_layouts(obj, old_count)
        representatives = [1, 2, 3, 4, 5, 4]
        new_colors = [old_colors[index - 1] for index in representatives]

        ENGINE.resize_project_filament_arrays(
            obj, old_count, representatives, layouts, old_colors, new_colors
        )

        self.assertEqual(layouts["filament_self_index"], ("slot", 3))
        self.assertEqual(layouts["filament_flow_ratio"], ("slot", 3))
        self.assertEqual(len(obj["filament_flow_ratio"]), 3 * len(representatives))
        self.assertEqual(obj["filament_flow_ratio"][-3:], ["4.0", "4.1", "4.2"])
        self.assertEqual(
            obj["filament_self_index"],
            [str(slot) for slot in range(1, len(representatives) + 1) for _ in range(3)],
        )

    def test_model_extruder_assignment_keeps_unpainted_slot_in_planning(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            metadata = folder / "Metadata"
            metadata.mkdir()
            (metadata / "model_settings.config").write_text(
                '<config><object id="1"><metadata key="extruder" value="4"/></object></config>'
            )

            slots = ENGINE.model_setting_extruder_slots(folder, 4)
            usage = ENGINE.include_model_extruder_usage({1: 1000}, slots)

            self.assertEqual(slots, {4})
            self.assertGreater(usage[4], 0)

    def test_model_extruder_assignment_ignores_automatic_slot_zero(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            metadata = folder / "Metadata"
            metadata.mkdir()
            (metadata / "model_settings.config").write_text(
                '<config><object id="1"><metadata key="extruder" value="0"/></object></config>'
            )

            self.assertEqual(ENGINE.model_setting_extruder_slots(folder, 4), set())

    def test_automatic_slot_zero_survives_conversion_and_validation(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            source = folder / "source.3mf"
            write_project(source)
            model_settings = (
                '<config><object id="1"><metadata key="extruder" value="0"/></object></config>'
            )
            with zipfile.ZipFile(source, "a", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("Metadata/model_settings.config", model_settings)

            output = ENGINE.convert(
                source,
                "official",
                palette_source="catalog",
                real_slots="2",
                output_dir=folder,
                reveal=False,
            )

            with zipfile.ZipFile(output["output"]) as archive:
                root = ENGINE.ET.fromstring(archive.read("Metadata/model_settings.config"))
            extruder = next(
                metadata for metadata in root.iter("metadata")
                if metadata.get("key") == "extruder"
            )
            self.assertEqual(extruder.get("value"), "0")

    def test_validator_rejects_saved_mixed_color_that_bambu_will_replace(self):
        obj = settings(3)
        obj["filament_colour"] = ["#EC008C", "#0A2E8A", "#9D5AC4"]
        obj["filament_multi_colour"] = obj["filament_colour"][:]
        obj["filament_is_mixed"] = ["0", "0", "1"]
        obj["filament_mixed_components"] = ["", "", "1,2"]
        obj["filament_mixed_sublayer_ratios"] = ["", "", "0.5000,0.5000"]
        with self.assertRaisesRegex(RuntimeError, "not Bambu-reconstructed"):
            ENGINE.validate_bambu_color_sync(obj, 2)

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
