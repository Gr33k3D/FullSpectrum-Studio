# FullSpectrum Studio 0.3 Community Preview

## Major Changes

- Preserves Bambu painted facets through decoded `paint_color` serialized state
  remapping and validates extended codes observed in original projects.
- Adds automatic or chosen `2-6` physical slot optimization, with mixed slots
  appended after physical slots and strictly limited to physical components.
- Adds local OBJ, GLB and texture reference analysis with an estimated visual
  similarity score.
- Replaces the previous RGB-root mixing preview with perceptual Lab
  interpolation and warns when owned filaments are only approximate CMYKW roles.
- Adds before/predicted orbitable preview switching on macOS and optional
  automatic opening of validated output.
- Adds safe archive extraction, preservation hashes, complete reopen validation,
  and regression tests.
- Adds a shared-engine Windows desktop shell plus portable ZIP and installer CI
  builds.
- Changes distribution to the PolyForm Noncommercial License 1.0.0.

## Verified Local Sample

A large painted angel project was converted against its GLB texture reference
without modifying its source archive. The automatic inventory mode selected
five physical filaments, passed geometry/resource preservation checks and
produced an estimated reference similarity score. Exact CMYKW and
inventory-CMYKW runs also reopened and validated successfully.

The sample files and inventory are deliberately not included in this public
repository.

## Limitations

- Predicted colors are estimates; filament translucency, surface finish,
  calibration and lighting affect the real print.
- OBJ and GLB are visual references, not direct printable-output inputs.
- Inventory integration depends on the local Bambu Studio Beta inventory format.
- Windows includes the conversion workflow but not the macOS SceneKit orbitable
  preview in this release.
- Catalog suggestions are not a promise of current stock in every region.
