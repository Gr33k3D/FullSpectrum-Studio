# FullSpectrum Studio v0.4 - v0.4.2 Final Report

## Release Decision

Version `0.4.0-community-preview` established the improved conversion and
validation workflow. Version `0.4.1-community-preview` fixed a large-project
loading regression. Version `0.4.2-community-preview` is the release to use:
it also fixes file-selection buttons that could fail to open a chooser in the
macOS app.

FullSpectrum remains:

```text
painted project -> palette reduction -> filament planning
-> mixed filament generation -> validated .3mf
```

It is not positioned as a slicer or as a calibrated universal color mixer.

## What Improved

- Bambu `paint_color` states are decoded and remapped from their serialized
  slot meaning; output is rejected unless the reopened archive has the exact
  expected decoded paint-state result.
- Color planning now uses CIEDE2000, dynamic physical anchors, predicted-gain
  thresholds and duplicate recipe reuse.
- The UI reports estimated quality, confidence, brightness/contrast
  preservation and pre-slice complexity, while refusing to invent print time,
  grams or swap counts without sliced data.
- The macOS viewer adds reduced/predicted, heatmap, anchor-influence and
  wireframe modes, render presets, model statistics, improved cancellation and
  clearer named filament recipes.
- Windows uses the same validated engine with aligned planning controls and
  reliable output reveal.
- Experimental textured OBJ and constrained embedded-texture GLB import
  preserve imported UV/texture meaning through the normal validation path and
  warn when extended source clusters must be compressed for export.

## Stabilization Results

- The real textured-OBJ preview peak memory fell from `590.2 MB` to `309.1 MB`
  after compact texture storage and streamed model XML.
- A large painted-project conversion with both analysis overlays dropped from
  `96.82 s` to `62.64 s` by reusing one preview geometry pass.
- A very large raw GLB is rejected in `0.05 s` and about `25.5 MB` rather than
  loading an input beyond the supported face limit.
- A `5,417,070`-triangle painted `.3mf` now opens metadata/palette in `0.06 s`;
  its optional interactive preview is declined in `3.96 s` at about `25.9 MB`
  rather than entering a memory-heavy viewer build.
- The automated suite contains `23` regression/security checks, including
  paint codec states, exact output remap validation, mixed-slot safety,
  bounded preview/analysis behavior, import behavior, deterministic schema
  output, unsafe archive rejection and report privacy.

Full measured results are in [BENCHMARK.md](BENCHMARK.md).

## Supported And Experimental

Supported:

- Painted Bambu Studio `.3mf` input.
- Local inventory, Bambu planning palette, exact CMYKW and custom palette
  planning sources.
- Optional OBJ, GLB or image reference scoring.
- macOS app and shared-engine Windows desktop build.

Experimental:

- Textured OBJ import with complete UVs and PNG/JPEG base-color texture.
- GLB import limited to uncompressed triangle primitives with positions, UVs,
  node transforms and one embedded texture.
- Optical-screen prediction mode, explicitly uncalibrated.

Unsupported or intentionally deferred:

- Image-only generation of printable geometry.
- Raw imports above the two-million-face limit.
- Broad compressed/multi-material GLB import.
- Exact visual claims without printer/material calibration.
- Print-time, purge-volume usage or filament-gram estimates before slicing.
- Synced side-by-side/UV viewer modes until they can be implemented and
  verified without weakening performance or trust.

## Privacy And Distribution

- The app reads local Bambu inventory only on the user's device and does not
  write local inventory paths or reference filenames into shareable reports.
- Public assets contain rendered model artwork only; they do not expose local
  file paths or inventory screens.
- The project is distributed under PolyForm Noncommercial 1.0.0 for
  non-commercial community use.

## Recommended v0.5 Direction

Do not broaden import formats first. The most useful next work is a small,
optional calibration workflow for owned filaments and mixed ratios, followed
by ingestion of slicer-generated time/purge/material statistics. Those two
items would turn current honest estimates into more practical print decisions
without changing FullSpectrum's identity.
