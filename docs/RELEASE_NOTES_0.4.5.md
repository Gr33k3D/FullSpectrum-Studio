# FullSpectrum Studio 0.4.5 Community Preview

This is a public packaging refresh for the v0.4.x community preview line.

## What changed

- Rebuilds the Windows portable and installer packages with the repaired
  PyInstaller configuration from v0.4.4.
- Names release downloads from the Git tag instead of a hardcoded v0.4.3
  filename, so each release page now matches the visible asset names.
- Updates existing release pages during repair runs so the release title and
  notes match the tag being published.

## Still included

- The v0.4.3 color synchronization fix remains the important correctness
  change: mixed-color preview and exported swatches follow Bambu Studio's
  loaded-color reconstruction.
- The source project is not modified; conversions write a copied 3MF plus CSV
  and validation report.

## Note on screenshots

The screenshots in the forum post were produced from a private validation model.
They are examples of the preview and validation views, not bundled sample input
files. A small public sample project can be added separately.
