# FullSpectrum Studio 0.4.2 Community Preview

## Button Reliability Fix

This is a small macOS UI reliability patch on top of v0.4.1. It does not
change paint remapping or the validated conversion rules.

- `Open Source` opens a native chooser for `.3mf`, `.obj` and `.glb`.
- `Reference` and `Add Reference` open a native chooser for visual reference
  models or images.
- `Add OBJ Texture` opens a native PNG/JPEG chooser.
- `Choose Library` opens a native JSON chooser for custom filaments.
- Attempting to compose a palette without a required input now opens the
  correct chooser instead of appearing inactive.

The earlier metadata-first large-file loading and bounded preview behavior from
v0.4.1 remain in place.

## Validation

- The shared conversion regression/security suite passes (`23` tests).
- The Swift macOS application builds and launches successfully.
- Live macOS UI checks confirmed that `Open Source` and `Reference` each open
  the correct native file chooser; the in-card actions reuse the same paths.
- Release packages remain stripped of local compiler path/debug symbols.
