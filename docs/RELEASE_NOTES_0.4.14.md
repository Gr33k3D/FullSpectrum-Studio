# FullSpectrum Studio v0.4.14 Official Release

Version 0.4.14 fixes automatic palette plans that could preserve large painted
regions while shifting a small black, white or other high-contrast detail too
far. It also hardens H2C project handling and makes copied support reports safe
to share.

## Detail Preservation

Automatic anchor selection now gives the largest visible color error more
weight. When another physical slot materially protects a small high-contrast
detail, Auto can use it instead of optimizing only for the much larger painted
regions. The reported quality score is also capped by the worst visible error,
and both mean and maximum estimated error are shown in the desktop apps.

Planning now includes object- and part-level filament assignments even when a
region has no explicit painted facets. Unused source colors no longer create
unused mixed-recipe slots.

## H2C Compatibility

Two-nozzle filament vectors and purge matrices are tested as complete slot
blocks when a converted palette changes size. A second-pass workflow that adds
or repaints a physical color, switches to H2C and converts again was also
validated. The generated project reopened with its geometry and color arrays
intact on the current Bambu Studio build used for validation.

A separately reported Bambu Studio `vector too long` / missing-geometry dialog
did not reproduce on that current build, so this release does not claim a
Bambu-side crash fix. The new regression protects the FullSpectrum metadata
path that can be verified locally.

## Privacy

Copy Error Report on macOS and Windows now omits local paths, model names,
inventory data, tracebacks and raw engine output. Detailed diagnostics remain
available only in a private local log. No user model, inventory export,
generated output, debug log or private screenshot is included in this release.

Windows packaging now uses Pillow `12.3.0`, which fixes the vulnerabilities
reported against `12.2.0`. The release workflow runs `pip-audit` before building
the Windows packages. The macOS ZIP is extracted and its app signature is
strictly verified before publication.

## Validation

- All `57` Python engine and desktop tests pass.
- The reported small-detail color shift is reproduced by a regression fixture
  and remains protected by the corrected automatic plan.
- H2C two-nozzle arrays and edited second-pass conversion are covered.
- The macOS Swift package builds in debug and release modes.
- The Windows shell compiles and imports without opening a GUI.
- The pinned Windows packaging dependencies pass `pip-audit` with no known
  vulnerabilities.
- GitHub Actions builds the macOS ZIP, Windows portable ZIP and Windows
  installer from the release tag.
