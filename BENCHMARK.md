# Validation Benchmark

## Method

These local checks were performed on 2026-05-27 on the development Mac.
Private project files, inventory data and generated outputs are not
distributed. Times and memory are regression observations, not general
hardware claims. Quality values are software estimates, not measured prints.

For every successful conversion, FullSpectrum reopens the written `.3mf` and
validates filament arrays, purge matrices, physical/mixed slot rules, paint
references, expected decoded paint remapping, source resources and
Bambu-reconstructed mixed display colors.

## Release Validation Matrix

| Scale | Input path exercised | Release outcome |
| --- | --- | --- |
| Small | Synthetic painted `.3mf` fixtures | Schema, remap, recipe reuse and Bambu color-sync tests pass |
| Medium | Textured OBJ and embedded-texture GLB fixtures | Validated import/output tests pass, including UV/texture handling |
| Large | Real painted `.3mf` plus GLB reference and overlays | Validated output; measured run below |
| Extreme | Oversized/unsafe archive and over-limit GLB fixtures | Rejected before unsafe or excessive decode/allocation |

## Final Large-Project Run

The final color-correctness and optimized-preview path was exercised with a
local painted angel project and read-only local inventory selection:

| Metric | Result |
| --- | ---: |
| Source triangles | `5,417,070` |
| Palette result | `6` physical + `11` mixed |
| Wall time | `66.37 s` |
| Peak resident memory | `100.3 MB` |
| Estimated quality / mean Delta E | `91.8 / 100` / `3.73` |
| Reference similarity / contrast retention | `86.4 / 100` / `81.0%` |
| Bambu saved-versus-loaded mix synchronization | maximum Delta E `0.00` |
| Maximum accepted mixed-target error | Delta E `7.70` |
| Unmatched painted colors | `6`, warned and kept out of misleading mixes |

The source includes purple painted regions. Under the chosen owned colors,
some purple and blue-green targets have no reliable reconstruction. This is
now surfaced as a limitation of the selected real palette rather than shown
as a convincing but inaccurate mixed swatch.

## Optimized Viewer Fallback

For the same large project, analysis visualization uses a
grid-reduced display mesh while processing and validation retain the full
project:

| Asset | Display vertices | Display faces | File size |
| --- | ---: | ---: | ---: |
| Color-loss heatmap | `30,604` | `71,389` | `2.3 MB` |
| Anchor-influence view | `30,604` | `71,389` | `2.3 MB` |

The UI identifies this state as `Using optimized preview for large models.`
This replaces the earlier blank/omitted large-model interactive view.
The predicted display reuses this validated proxy geometry and replaces only
its materials, avoiding another full-surface viewer extraction after export.

## Regression Suite

```bash
python3 -m unittest discover -s tests -v
./script/build_and_run.sh verify
```

The current suite passes `28` automated tests, including purple, green,
orange, neutral and dark Bambu reconstruction checks; rejection of an
unreliable purple mix; exact paint remapping; component/array/purge
validation; optimized-preview fallback; OBJ/GLB behavior; deterministic
output; archive defenses and shareable-report privacy.

## Viewer Notes

The native viewer exposes `Fast`, `Balanced`, `High` and `Maximum` render
presets. Actual display frame rate depends on the Mac and model complexity;
no FPS claim is made here.

Use slicer results and a small printed calibration piece before committing
large material volumes to a color-sensitive print.
