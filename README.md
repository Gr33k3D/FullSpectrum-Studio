# FullSpectrum Studio

FullSpectrum Studio is a local desktop workflow for reducing the physical
filament count of painted Bambu Studio `.3mf` projects while trying to preserve
their original painted appearance.

It creates a separate converted `.3mf`, a recipe CSV and a validation report.
The source project is never modified.

This is an independent community preview built around the H2C public-beta
workflow and is not affiliated with Bambu Lab.

Latest reliability update: [v0.4.1 Community Preview](https://github.com/Gr33k3D/FullSpectrum-Studio/releases/tag/v0.4.1-community-preview).

## What It Does

- Reads Bambu serialized `paint_color` states from the model itself instead of
  assuming that paint order equals filament order.
- Chooses `2-6` physical filament anchors automatically or manually, then adds
  only mixed recipes whose estimated visual gain justifies the extra logical
  color. Identical recipes reuse one slot.
- Supports local Bambu Studio Beta inventory in read-only mode, Bambu PLA
  planning palettes, CMYKW workflows and custom local filament libraries.
- Accepts an optional `.obj`, `.glb` or texture image as a visual reference and
  reports estimated similarity, brightness, contrast and confidence.
- Imports constrained textured `.obj` and embedded-texture `.glb` sources
  experimentally as new painted projects, routed through the same validator.
- Provides movable original, reduced/predicted, heatmap, anchor-influence and
  wireframe previews on macOS.
- Opens large painted projects through a quick thumbnail/palette pass and
  omits optional 3D overlays above a practical triangle budget rather than
  forcing a slow, memory-heavy viewer build.

## Preview

![Source preview, estimated color-loss heatmap and anchor-influence overlay](https://github.com/Gr33k3D/FullSpectrum-Studio/releases/download/v0.4.0-community-preview/FullSpectrum-angel-analysis-v0.4.png)

Preview estimates from a validated local test project; this is not a calibrated
printed-color measurement.

The displayed analysis image was produced with v0.4; v0.4.1 preserves that
workflow and adds the large-file loading guard.

## Validation

Every output is reopened before it is accepted. The engine rejects output if:

- A `paint_color` state refers to a slot that does not exist.
- A mixed slot references itself, another mixed slot, duplicate components or
  components outside the physical slots.
- Filament arrays or purge matrices are misaligned, or a generated purge
  matrix contains a zero off-diagonal transition.
- Written paint states do not equal the exact expected decoded remap.
- Existing geometry, UV-bearing model data or source textures/resources change
  beyond permitted paint remapping.

Archive extraction is defensive and rejects unsafe archive paths and excessive
uncompressed archive sizes.

## Filament Choices

### My Inventory

Recommended for practical printing. Uses active PLA spools detected in the
local Bambu Studio Beta inventory and estimates available mixing capacity from
remaining material.

### Bambu Core

Plans with supported PLA Basic, PLA Matte and PLA Silk+ colors.

### All Bambu

Allows additional Bambu PLA families discovered locally. Catalog colors are
planning suggestions only; confirm current regional availability before buying.

### CMYKW

`Exact CMYKW` assigns literal CMYKW roles. `CMYKW` with inventory maps those
roles to owned colors and warns when a match is poor.

### Custom Brands

Accepts a JSON file in the format shown at
[examples/custom-palette.example.json](examples/custom-palette.example.json).

Mixed-color previews and quality scores are estimates, not printer
calibration. Version 0.4 uses CIEDE2000 for comparison and offers a conservative
default prediction plus an opt-in, uncalibrated optical-screen experiment.

## Reference And Source Import

Reference mode samples texture information from a `.glb`, an OBJ material
texture or an image, then compares dominant colors with the predicted reduced
palette. It can help choose a palette without changing the project's geometry.

Experimental textured source import creates a printable painted-project
candidate:

- OBJ requires complete UVs and a PNG/JPEG base-color texture. If its material
  link is missing, the app lets the user choose the base-color texture
  explicitly.
- GLB currently accepts uncompressed triangle primitives with positions, UVs,
  node transforms and one embedded texture.
- Images by themselves do not contain printable geometry.
- Imports over two million faces are rejected; very large raw GLBs remain
  useful as references to an already practical painted `.3mf`.
- Automatic interactive and analysis previews are omitted above `750,000`
  triangles; conversion and validation remain available.

## Printability Reporting

FullSpectrum reports logical mixed slots, painted mixed share, purge-transition
context and a pre-slice complexity rating. It does not guess exact print time,
swap count or filament grams from an unsliced painted project; those require
sliced toolpaths.

The quality-versus-waste control lets the user decide whether a predicted
improvement is worth additional logical mixed colors.

## macOS App

Requirements:

- macOS 14 or newer
- Swift 5.9 / Xcode command-line tools
- Python 3 supplied with macOS

```bash
./script/build_and_run.sh build
./script/build_and_run.sh run
```

The application is written to `dist/FullSpectrum Studio.app`. Community
preview ZIPs are ad-hoc signed rather than notarized.

## Windows App

Windows uses the same Python conversion and validation engine in a compact
desktop shell. Tagged releases build a portable ZIP and installer through
[.github/workflows/windows-release.yml](.github/workflows/windows-release.yml).
The macOS orbitable analysis viewer is not present in the Windows UI.

## Command Line

Painted `.3mf` conversion with a visual reference:

```bash
python3 fullspectrum_engine.py --mode official --palette-source inventory \
  --real-slots auto --quality-bias 60 --reference original.glb painted-project.3mf
```

Experimental textured OBJ import:

```bash
python3 fullspectrum_engine.py --mode official --palette-source catalog \
  --quality-bias 60 textured-source.obj
```

Reproducible local planning variants:

```bash
python3 tools/benchmark_quality.py --reference original.glb painted-project.3mf
```

## Privacy And Safety

- Inventory access is local and read-only. No spool identifiers or local
  inventory paths are written to generated shareable reports.
- Packaged macOS executables are stripped of local build-path/debug symbols
  before release archives are produced.
- Private model projects, generated outputs, inventories and private
  screenshots are not committed to this repository.
- Before printing, verify filament assignments, purge settings and slicing in
  Bambu Studio; physical appearance still depends on filament and calibration.

## Documentation

- [Final Report](FINAL_REPORT.md)
- [Benchmark](BENCHMARK.md)
- [Changelog](CHANGELOG.md)
- [Research](RESEARCH.md)
- [Ideas](IDEAS.md)
- [Roadmap](ROADMAP.md)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Validation And Testing](docs/VALIDATION.md)
- [Security And Privacy](docs/SECURITY_PRIVACY.md)
- [0.4 Release Notes](docs/RELEASE_NOTES_0.4.md)
- [0.4.1 Reliability Notes](docs/RELEASE_NOTES_0.4.1.md)

## License

Released under the [PolyForm Noncommercial License 1.0.0](LICENSE). It is
shared for non-commercial community use and modification; it is not an
OSI-approved open-source license and does not permit commercial exploitation.
