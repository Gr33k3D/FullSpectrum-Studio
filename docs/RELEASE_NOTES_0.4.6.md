# FullSpectrum Studio 0.4.6 Community Preview

This is the corrected public package for the v0.4.x community preview line.

## What changed

- Stamps the macOS app bundle version from the release tag, so the downloaded
  app reports the same version as the GitHub release and ZIP filename.
- Keeps the v0.4.5 release workflow fix that names downloads from the Git tag.
- Keeps the v0.4.4 Windows PyInstaller packaging repair.

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
