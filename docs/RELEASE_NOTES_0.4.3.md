# FullSpectrum Studio 0.4.3 Community Preview

## Critical Mixed-Color Correction

Earlier preview math could select and display a mixed color that Bambu Studio
replaced when the exported file was opened. Version 0.4.3 uses Bambu-compatible
mixed-filament swatch reconstruction throughout planning, export and preview.

- Mixed color decisions now use the serialized recipe ratios Bambu loads.
- `filament_colour` and `filament_multi_colour` are written from one
  reconstruction path.
- The generated archive is reopened and rejected if a mixed swatch would be
  changed by Bambu's reconstruction.
- A mix is no longer proposed when its Bambu-reconstructed output remains more
  than Delta E `8` from its painted target. The app keeps the closest physical
  option and explains that a closer filament is needed.
- The macOS app includes a Validation preview mode and Color Debug View.
- Every output includes a `*_COLOR_VALIDATION.md` report.

## Viewer And Large Models

- The viewer is now the central workspace, with collapsible tools and activity
  output plus a fullscreen control.
- Detailed original plate rendering remains selectable alongside an optimized
  movable 3D representation on extreme projects.
- Recipes show painted target and Bambu-reconstructed output as two separate
  swatches.
- Large painted projects no longer fall back to a blank viewport: they receive
  an automatically grid-reduced optimized preview and optimized analysis overlays.
  Conversion and validation still inspect the full archive.
- The reduced/predicted view reuses the validated analysis geometry after
  conversion, avoiding another expensive large-model preview rebuild.

## Verification

- The compatibility reconstruction matches the mixed swatches Bambu Studio
  loaded for the local angel benchmark file.
- Regression tests cover purple, green, orange, neutral and dark mixes, along
  with the real benchmark recipes.
- A regression protects the case where a purple painted target cannot be
  accurately produced from the chosen real colors.
- The normal paint, geometry/texture preservation, archive safety, OBJ/GLB and
  resource-budget regressions remain enabled.

## Limitations

This corrects the application-versus-Bambu displayed color mismatch. A real
print can still differ from both previews due to material and printing
conditions; use a small calibration sample for sensitive color work.
