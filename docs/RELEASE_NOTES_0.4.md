# FullSpectrum Studio 0.4 Community Preview

## Direction

FullSpectrum remains a converter for painted projects: it reduces a physical
palette, plans mixed colors and validates a separate Bambu-compatible `.3mf`.
It is not a replacement slicer and does not copy Prusa ColorMix or an Orca
fork.

## Changes

- Uses CIEDE2000 for perceptual color comparisons and adds confidence,
  brightness-error and contrast-retention estimates.
- Adds a quality-versus-waste control. Weak mix improvements are suppressed,
  identical recipes reuse one logical slot, and high-detail three-color
  candidates remain opt-in through the detail setting.
- Adds an opt-in optical-screen prediction experiment, labelled uncalibrated;
  conservative perceptual estimation remains the default.
- Uses optional texture-reference colors as a limited contribution to physical
  anchor selection.
- Adds heatmap, anchor-influence and wireframe viewer modes, model statistics
  and cancellable conversion in the macOS app.
- Adds printability complexity reporting and explicitly avoids fabricated
  pre-slice time, swap and filament-use values.
- Adds experimental constrained textured OBJ/GLB import with UV/texture
  preservation, deterministic texture clustering and Bambu slot compression
  warnings, including an explicit OBJ base-color texture picker for exports
  without a material-library link.
- Validates that output paint states exactly equal the decoded expected remap
  after the written archive is reopened.
- Aligns Windows controls and reporting with the updated shared engine.

## Verified Private Sample

A large locally held painted angel project was converted with its texture
reference using the Balanced setting. The output reopened successfully with:

- `3` physical slots and `6` mixed logical slots.
- Estimated quality `85.5 / 100`, reference similarity `86.7 / 100` and
  confidence `82.4 / 100`.
- Geometry, UV/resource preservation and decoded paint-remap equivalence
  verified.

These are planning estimates, not measured printed color. The private source
model, inventory and generated report are not included in this repository.
The Detail setting estimated `88.9 / 100` quality with `5` physical and `11`
mixed slots at higher complexity; Balanced intentionally did not add those
slots automatically. See [BENCHMARK.md](../BENCHMARK.md).

## Limits

- Physical mixed-color appearance still needs calibration or a small test
  print for the chosen material and printer.
- GLB import supports a constrained embedded-texture triangle subset and
  rejects unsupported primitives/material structures or sources above the
  two-million-face safety limit explicitly.
- PNG/JPG images do not create printable geometry by themselves.
- Actual time, swap count, purge usage and filament grams require slicing.
- Catalog choices require the user to confirm local availability.

## Moving From 0.3

- Keep the original painted `.3mf` and run it through v0.4; do not edit an
  older generated output in place.
- v0.4 may deliberately emit fewer mixed logical slots than v0.3 because a mix
  is now added only when its predicted visual gain clears the selected
  quality-versus-waste threshold.
- Existing v0.3 outputs remain ordinary files, but v0.4 validation and
  analysis reporting apply only to files converted again with the v0.4 engine.
