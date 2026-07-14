# FullSpectrum Studio

FullSpectrum Studio is a local desktop workflow for reducing the physical
filament count of painted Bambu Studio `.3mf` projects while trying to preserve
their original painted appearance.

It creates a separate converted `.3mf`, a recipe CSV and a validation report.
The source project is never modified.

This is an independent community release built around the H2C public-beta
workflow and is not affiliated with Bambu Lab.

Latest public package: [v0.4.16 Official Release](https://github.com/Gr33k3D/FullSpectrum-Studio/releases/tag/v0.4.16).
See the [v0.4.16 release notes](docs/RELEASE_NOTES_0.4.16.md) for the newer H2C
project compatibility fix.

## What It Does

- Reduces and remaps existing Bambu painted `.3mf` projects. FullSpectrum does
  not repaint a model, smooth noisy paint regions or clean up a bad source
  paint job; it preserves the existing paint states as honestly as it can while
  reducing the filament plan.
- Reads Bambu serialized `paint_color` states from the model itself instead of
  assuming that paint order equals filament order.
- Chooses `2-6` physical filament anchors automatically or manually, then adds
  only mixed recipes whose estimated visual gain justifies the extra logical
  color. Identical recipes reuse one slot.
- Auto does not increase the physical filament count of projects with six or
  fewer active source colors. Explicit manual slot choices remain available.
- Smart quality mode automatically compares practical, balanced, detail and
  high-detail plans, then keeps the best validated result for the model's
  painted usage.
- Supports local Bambu Studio Beta inventory in read-only mode, Bambu PLA
  planning palettes, CMYKW workflows and custom local filament libraries.
- Accepts an optional `.obj`, `.glb` or texture image as a visual reference and
  reports estimated similarity, brightness, contrast and confidence.
- Imports constrained textured `.obj` and embedded-texture `.glb` sources
  experimentally as new painted projects, routed through the same validator.
- Provides the original plate render plus movable original, reduced/predicted,
  validation, heatmap, anchor-influence and wireframe previews on macOS.
- Reconstructs mixed swatches with Bambu Studio's `FilamentMixer` model and
  exports a color-validation report for app/export/Bambu comparisons.
- Keeps a mixed recipe only when Bambu's reconstructed color is within a
  reliable match threshold; otherwise it keeps the nearest physical anchor
  and warns that an additional real filament is needed.
- Opens large painted projects through a quick thumbnail/palette pass and
  builds a grid-reduced, memory-bounded movable preview instead of leaving the
  viewer blank or forcing a full multi-million-triangle display build.
- Can hand a validated output directly to Bambu Studio or OrcaSlicer when the
  selected slicer is installed.

Very complex or noisy painted files can still be hard cases: conversion may be
slow, and the result can only be as clean as the source paint-state data it is
asked to remap. Current builds write detailed diagnostics only to a private
local log. The copyable support report excludes local paths, model names,
inventory data and raw engine output.

## Preview

![FullSpectrum Studio predicted preview and palette validation](teasers/v0.4.3-predicted.png)

Preview estimates from a validated local test project; this is not a calibrated
printed-color measurement. Screenshots demonstrate view modes from a detail
run; the documented benchmark uses its stated validated planning setting, so
logical mixed-slot counts can differ.

Version v0.4.3 centers the viewer, adds fullscreen viewing and color-debug
comparison, displays target and exported mixed swatches separately, and
corrects mixed-color preview synchronization with Bambu Studio.

Additional real-project views:
[original plate](teasers/v0.4.3-original.png) |
[validation](teasers/v0.4.3-validation.png) |
[color-loss heatmap](teasers/v0.4.3-heatmap.png) |
[anchor influence](teasers/v0.4.3-anchor.png)

## Validation

Every output is reopened before it is accepted. The engine rejects output if:

- A `paint_color` state refers to a slot that does not exist.
- A mixed slot references itself, another mixed slot, duplicate components or
  components outside the physical slots.
- Filament arrays or purge matrices are misaligned, or a generated purge
  matrix contains a zero off-diagonal transition.
- Written paint states do not equal the exact expected decoded remap.
- `filament_colour` and `filament_multi_colour` disagree, or any saved mixed
  swatch differs from the color Bambu reconstructs from its recipe.
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

Plans with supported PLA Basic, PLA Matte and PLA Silk+ colors. Choose the
catalog planning region in the app so reports and warnings match the market
you intend to check.

### All Bambu

Allows additional Bambu PLA families discovered locally. Catalog colors are
planning suggestions only; FullSpectrum does not check live store stock, so
confirm current regional availability before buying.

### CMYKW

`Exact CMYKW` assigns literal CMYKW roles. `CMYKW` with inventory maps those
roles to owned colors and warns when a match is poor.

### Custom Brands

Accepts a JSON file in the format shown at
[examples/custom-palette.example.json](examples/custom-palette.example.json).

Mixed-color previews now use the same Bambu Studio reconstruction model as the
saved recipe display color. Quality scores still estimate closeness to the
source, not a calibrated physical print: material, layers and lighting remain
real-world variables.

## How Color Mixing Works

FullSpectrum does not create continuous, chemical filament blends. It uses
Bambu-style mixed filament slots, which behave more like 3D halftoning: a
logical mixed slot references two or three physical base filaments, and the
printer alternates very thin sublayers according to the saved component
ratios. At normal viewing distance the eye averages those sublayers into a
new perceived color, similar to how 2D CMYK printing uses discrete ink dots to
suggest continuous tones.

The search is not "try every filament combination forever." The engine first
builds a candidate pool from the selected source: owned inventory, Bambu Core,
All Bambu or a custom JSON library. For Bambu catalog planning it reads the
installed Bambu Studio color-code catalog when available, so candidates are
real Bambu color entries instead of guessed names. It then shortlists likely
anchors by looking at the source paint colors, their painted usage, optional
reference colors, luminance coverage, dark/light coverage and saturated color
coverage. The shortlist is split into hue/neutral spectrum compartments so
important reds, blues, warm neutrals or darks do not disappear just because a
single global nearest-color score liked another region more. A beam/greedy pass
proposes physical anchor sets, and Best mode adds one swap-refinement pass to
replace weak anchors after the final mixed-palette score is known.

Best mode also builds a target-aware in-memory mix database for the active
candidate pool. Pair and likely three-color Bambu halftone recipes are
reconstructed once, scored against the source paint colors, then reused while
the anchor beam tests thousands of possible physical-slot sets. This matters
because the 32-slot output limit is not the slow part; repeatedly recomputing
the same Bambu mix recipes during anchor selection is.

Smart quality is adaptive. Instead of always walking every quality band, it
probes the spectrum around `70/100`, checks whether the result is too inaccurate
or too wasteful, then jumps toward lower-waste or higher-fidelity bands only
when they can plausibly improve the score. The conversion report lists which
bands were tested and which were skipped.

For each source paint color, FullSpectrum compares the nearest physical anchor
against a small set of possible mixed recipes. These recipes are intentionally
discrete. Bambu stores normalized ratios, then reconstructs mixed swatches from
integer percentage weights, and arbitrary ratios such as 30:70 imply longer
layer cadence patterns that can reduce vertical color resolution and increase
print complexity. Practical planning therefore uses simple repeatable ratios:
`1:3`, `1:2`, `1:1`, `2:1` and `3:1` for two-color mixes. Detail/Best mode can
also test denser but still bounded schedules such as `1:5`, `1:4`, `2:3`,
`3:2`, `4:1`, `5:1`, plus selected three-color ratios including `1:1:1`,
`3:1:1`, `2:2:1` and nearby permutations. It only keeps a mixed slot when it
beats the nearest physical anchor by enough Delta E, stays inside the current
quality-vs-waste threshold and fits within Bambu's paint-slot limit.

The predicted swatch is reconstructed with Bambu Studio's `FilamentMixer`
model, not a hand-written Yule-Nielsen implementation. Yule-Nielsen-style
optical models are useful for explaining halftone reflectance, but the current
app must match what Bambu Studio reloads from the `.3mf`; otherwise the UI can
show one color while Bambu shows another. That is why every output is reopened
and checked so saved mixed colors match the Bambu-reconstructed colors.

Calibration still matters. Real prints can drift because filament opacity,
surface texture, layer height, temperature, lighting, dark/light interaction,
saturation loss and hue drift are physical effects. If new measured mix colors
are added later, they should be fitted back into the model, or into an explicit
calibration correction layer, instead of just adding more theoretical ratios.

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
- Large `.3mf` projects use an automatically grid-reduced optimized preview and
  optimized analysis overlays. Palette conversion and archive validation
  still use the full project data.

## Printability Reporting

FullSpectrum reports logical mixed slots, painted mixed share, purge-transition
context and a pre-slice complexity rating. It does not guess exact print time,
swap count or filament grams from an unsliced painted project; those require
sliced toolpaths.

Smart quality mode is the recommended default. It tries practical, balanced and
detail thresholds adaptively, scores the final palette after mixed recipes are
generated, and selects the best tradeoff for the painted usage in that model.
Manual quality-versus-waste values are still available when you want to force a
simpler or more detailed result.

The macOS app also has a planning-sample option. `Paint states` uses the
original decoded Bambu paint usage. `Render preview` uses the same optimized
preview mesh built for the viewport as a visual weighting sample, so large
visible regions matter more during anchor selection. This is still only a
planning weight: the exported `.3mf` is always written from the original decoded
Bambu paint states, not from a screenshot or inferred repaint.

## macOS App

Requirements:

- macOS 14 or newer
- Swift 5.9 / Xcode command-line tools
- Python 3 supplied with macOS

```bash
./script/build_and_run.sh build
./script/build_and_run.sh run
```

The application is written to `dist/FullSpectrum Studio.app`. The viewer is
the primary workspace, with collapsible tools and activity log plus fullscreen
preview for screenshots and close visual inspection. The movable 3D viewport
uses an H2C-oriented 330 x 320 Textured PEI plate reference because this build
is tuned around the H2C workflow. Community preview ZIPs have a verified ad-hoc
bundle signature; they are not Developer ID notarized.

## Windows App

Windows uses the same Python conversion and validation engine in a compact
desktop shell. Tagged releases build a portable ZIP and installer through
[.github/workflows/windows-release.yml](.github/workflows/windows-release.yml).
The Windows shell can run a dry Preview Plan before conversion and shows the
selected anchors, quality, printability and warnings without writing a 3MF.
The macOS orbitable analysis viewer is not present in the Windows UI.

## OrcaSlicer Handoff

The app now offers `OrcaSlicer` as an output destination. FullSpectrum still
does the palette reduction and validation first, then opens the separately
saved `.3mf` in an installed OrcaSlicer application.

This is intentionally a file handoff, not an OrcaSlicer plugin. Validation of
Bambu mixed-filament loaded swatches remains Bambu-specific; when opening a
FullSpectrum file in OrcaSlicer, inspect filament assignments and slice a
small test before committing to a color-sensitive print. See
[docs/ORCASLICER_HANDOFF.md](docs/ORCASLICER_HANDOFF.md).

## Command Line

Painted `.3mf` conversion with a visual reference:

```bash
python3 fullspectrum_engine.py --mode official --palette-source inventory \
  --real-slots auto --quality-bias auto --reference original.glb painted-project.3mf
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

- Inventory access is local and read-only. No spool identifiers, quantities or
  local inventory paths are written to generated shareable text reports.
- Packaged macOS executables are stripped of local build-path/debug symbols
  before release archives are produced.
- Private model projects, generated outputs, inventories and private
  screenshots are not committed to this repository.
- Copyable error reports omit local paths, model names, inventory data and raw
  engine output; full diagnostics remain in a private local log.
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
- [Color Validation](COLOR_VALIDATION.md)
- [Third-Party Notices](THIRD_PARTY_NOTICES.md)
- [Security And Privacy](docs/SECURITY_PRIVACY.md)
- [0.4 Release Notes](docs/RELEASE_NOTES_0.4.md)
- [0.4.16 Release Notes](docs/RELEASE_NOTES_0.4.16.md)
- [0.4.15 Release Notes](docs/RELEASE_NOTES_0.4.15.md)
- [0.4.14 Release Notes](docs/RELEASE_NOTES_0.4.14.md)
- [0.4.13 Release Notes](docs/RELEASE_NOTES_0.4.13.md)
- [0.4.12 macOS H2C Notes](docs/RELEASE_NOTES_0.4.12_MACOS.md)
- [0.4.9 Release Notes](docs/RELEASE_NOTES_0.4.9.md)
- [0.4.1 Reliability Notes](docs/RELEASE_NOTES_0.4.1.md)
- [0.4.2 Button Fix Notes](docs/RELEASE_NOTES_0.4.2.md)
- [0.4.3 Color Synchronization Notes](docs/RELEASE_NOTES_0.4.3.md)
- [0.4.7 CMYKW Quality Notes](docs/RELEASE_NOTES_0.4.7.md)
- [0.4.8 Reliability Notes](docs/RELEASE_NOTES_0.4.8.md)
- [OrcaSlicer Handoff](docs/ORCASLICER_HANDOFF.md)
- [Bambu Forum Update Draft](docs/BAMBU_FORUM_POST_v0.4.3.md)
- [Bambu Forum Reliability Reply Draft](docs/BAMBU_FORUM_REPLY_RELIABILITY_2026-05-30.md)

## License

Released under the [PolyForm Noncommercial License 1.0.0](LICENSE). It is
shared for non-commercial community use and modification; it is not an
OSI-approved open-source license and does not permit commercial exploitation.
