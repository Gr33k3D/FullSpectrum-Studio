# FullSpectrum Studio v0.5.0 Official Release

Version 0.5.0 makes palette planning automatic and visible before conversion.
It also makes My Inventory behavior explicit when an important color is not
available in Bambu Studio's active Filament Manager entries.

## Automatic Live Forecast

- Best planning and render-preview weighting are the default workflow.
- Changing the source model, filament source, physical-slot count, quality or
  palette schedules a debounced forecast automatically.
- macOS displays the predicted reduced-color model in the movable 3D viewer.
- The forecast reports estimated accuracy, confidence, maximum visible Delta E,
  expected swatches and the physical-plus-mixed slot plan.
- Plan-only analysis can generate predicted, color-loss and anchor-influence
  meshes without writing a converted `.3mf`.

Estimated accuracy compares the planned palette with the source paint colors.
It is useful for comparing plans, but it is not a calibrated guarantee of the
printed result. Filament opacity, printer settings, layer geometry and lighting
can all change physical color.

## Inventory Guidance

My Inventory intentionally plans only with compatible active PLA colors found
in Bambu Studio's Filament Manager. If a key color is absent, FullSpectrum now
shows the worst target-to-predicted match and recommends a substantially closer
filament. The UI says whether that suggestion is already in My Inventory or is
available only from the broader Bambu catalog, and can apply the suggestion to
the plan.

## Redesigned Desktop Apps

- macOS keeps automatic forecasts in the Plan workspace, overlays the estimated
  accuracy on the viewer and presents expected swatches and inventory guidance
  beside the planning controls.
- Windows uses a new split workspace with a source thumbnail, accuracy gauge,
  confidence and error metrics, expected palette swatches, slot summary and an
  actionable missing-filament notice.
- Manual Preview Plan remains available on both platforms. Stale automatic
  results are discarded when planning controls change.

## Compatibility And Validation

- The 0.4.16 fix for newer H2C three-value filament setting vectors remains in
  place, preventing the Bambu Studio `vector` import error when output filament
  counts change.
- The bundled engine no longer writes Python bytecode inside the signed macOS
  app, preserving its resource seal after forecasts and conversions run.
- All 62 automated engine and desktop tests pass.
- The macOS app and extracted release archive pass strict ad-hoc signature
  verification. Windows portable and installer packages are built and checked
  by the tagged release workflow.
- No submitted model, filename, inventory content, local path, private log,
  account detail or private screenshot is included in the release.
