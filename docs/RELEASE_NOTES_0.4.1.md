# FullSpectrum Studio 0.4.1 Community Preview

## Reliability Update

This patch keeps the v0.4 conversion and validation behavior, while fixing a
loading regression in the macOS app.

- Painted `.3mf` sources now load palette/thumbnail metadata first, so a
  project is usable before optional interactive preview work begins.
- Automatic interactive and analysis overlay meshes are bounded at `750,000`
  triangles. Larger projects keep their plate preview and remain convertible
  and validatable without a viewer memory spike.
- Modest textured OBJ/GLB sources appear immediately while paint analysis
  continues in the background.
- Old cancelled preview work can no longer replace a newly selected model.
- Imported local files use narrowly scoped macOS read access while processing.

## Verified Regression Case

A local painted `.3mf` with `5,417,070` triangles previously entered a
long-running automatic viewer build on open. In v0.4.1, metadata/palette open
completed in `0.06 s`, and the bounded preview check completed in `3.96 s`
using approximately `25.9 MB` peak resident memory while correctly declining
the optional mesh.

The source model is not included. All conversion schema, paint-remap and
reopen-validation checks remain in place.

## Limits

- Omitted overlays are a viewer safeguard, not a failure of the printable
  output.
- Textured OBJ/GLB source import remains experimental.
- Mixed-color appearance estimates still require a material test print for
  physical confirmation.
