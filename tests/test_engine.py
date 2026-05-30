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

    def test_quality_mix_limit_is_conservative_until_quality_is_raised(self):
        self.assertEqual(ENGINE.quality_mix_limit(60),ENGINE.MAX_RELIABLE_MIX_DE)
        self.assertEqual(ENGINE.quality_mix_limit(100),ENGINE.MAX_HIGH_QUALITY_MIX_DE)

    def test_rejects_misleading_mixed_recipe_even_when_it_beats_bad_anchors(self):
        anchors=[
            {"name":"Black","color":"#000000"},
            {"name":"Pink","color":"#BA9594"},
        ]
        palette=ENGINE.build_palette(["#335599"],anchors,{1:100},100)
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
