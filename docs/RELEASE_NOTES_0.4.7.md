# FullSpectrum Studio 0.4.7 Community Preview

## CMYKW Quality-100 Fix

Version 0.4.7 fixes a CMYKW palette reduction failure where quality `100`
could reject useful mixed recipes and remap large warm painted regions to the
nearest physical white or warm-white slot.

- The mix reliability threshold now follows the quality slider.
- Default quality keeps the earlier conservative Delta E `8` gate.
- Quality `100` allows moderate CMYKW blends up to Delta E `14` when they
  produce a clear visual gain.
- The real benchmark file now keeps its source bright-paint share instead of
  collapsing most painted facets to warm white.
- Output filenames now use the `v0.4.7` engine stamp.

## Packaging

- macOS release ZIPs are created without resource-fork or Finder metadata
  payloads, reducing the chance of local extended attributes interfering with
  ad-hoc signature verification after download.
- Windows and macOS tagged releases continue to build from source through the
  shared release workflow.

## Verification

- Added a regression that reproduces the warm-tone CMYKW quality-100 collapse
  and confirms the tan/brown slots become mixed recipes rather than warm white.
- Regression coverage still rejects genuinely misleading mixed recipes even
  when they beat poor physical anchors.
- The full engine test suite passes with `python3 -m unittest discover -s tests`.
- Local macOS ZIP/extract verification confirms the v0.4.7 app bundle reports
  version `0.4.7` and passes strict ad-hoc signature verification after a
  metadata-free ZIP round trip.
