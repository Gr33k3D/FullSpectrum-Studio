# Core Extraction Plan

This plan documents what can be extracted from the current macOS SwiftUI app
and Python engine into reusable contracts for the Tauri Windows desktop shell.

## Current macOS Code Survey

### Project Model Structures

Source: `Sources/FullSpectrumStudio/Models/StudioModels.swift`

Reusable:

- `ProjectInspection`
- `MeshMetrics`
- `ConversionResult`
- `InventorySnapshot`
- `InventorySpool`
- `QualityMetrics`
- `PrintabilityMetrics`
- `PreservationResult`
- `AnalysisAssets`
- `ImportSummary`
- `ReferenceSummary`
- `AnchorFilament`
- `RecipeItem`
- `ConversionProgress`

Extraction approach:

1. Treat these as the current JSON DTO source of truth.
2. Mirror them in TypeScript before changing engine output.
3. Add Rust equivalents only at the bridge boundary.
4. Keep platform UI enums separate from engine DTOs unless they appear in
   engine JSON.

Manual review:

- `filamentID` casing differs from typical Rust/TypeScript naming.
- `import` requires escaped identifiers in Swift and JS/Rust model care.
- Some optional metrics are absent for metadata-only inspection.

### Asset Loading and Parsing

Sources:

- `fullspectrum_engine.py`
- `Sources/FullSpectrumStudio/Services/ConverterService.swift`
- `Sources/FullSpectrumStudio/Stores/StudioStore.swift`

Current behavior:

- Swift selects files with `NSOpenPanel`.
- Swift calls Python via `ConverterService`.
- Python owns archive safety, `.3mf` parsing, OBJ/GLB inspection, texture
  sampling, preview mesh generation and validation.

Extraction approach:

1. Do not reimplement archive parsing in React.
2. Add Tauri Rust commands that call the existing Python CLI first.
3. Stabilize JSON contracts for:
   - project metadata
   - asset list
   - preview assets
   - conversion progress
   - conversion result
4. Only then port hot paths from Python to Rust.

Manual TODO:

- Port Bambu `.3mf` path safety rules exactly.
- Preserve Bambu `paint_color` codec behavior; do not reintroduce formula or
  first-use mapping guesses.

### Renderer State Models

Sources:

- `Sources/FullSpectrumStudio/Views/InteractiveModelView.swift`
- `Sources/FullSpectrumStudio/Views/ModelPreviewCard.swift`
- `StudioStore.previewMode`
- `StudioStore.viewerPerformance`

Current behavior:

- macOS uses SceneKit.
- Viewer performance modes are `fast`, `balanced`, `high`, `maximum`.
- Preview modes include original, predicted, validation, heatmap, anchor
  influence and wireframe.
- Large models can fall back to optimized preview meshes.

Extraction approach:

1. Define renderer state as data, not UI:
   - backend
   - status
   - view mode
   - performance mode
   - loaded asset path
   - capabilities
   - warnings
2. Keep SceneKit implementation macOS-only.
3. Keep Tauri React renderer placeholder honest until the preview asset
   contract is wired.
4. Add `wgpu` only after bounded memory and cancellation rules are defined.

Manual TODO:

- Preserve large-model fallback thresholds and user-facing notices.
- Match Bambu loaded-color reconstruction for any predicted swatches.

### Settings and Configuration

Sources:

- `PaletteMode`
- `PaletteSource`
- `RealSlotSelection`
- `MixPrediction`
- `OutputApplication`
- `PreviewMode`
- `ViewerPerformance`
- `@AppStorage` keys in `StudioStore`

Reusable settings:

- palette strategy
- filament source
- physical slot selection
- quality bias
- mix prediction model
- output application
- auto-open result
- restore last session
- renderer performance
- preview mode

Extraction approach:

1. Add `AppSettings` to TypeScript and Rust.
2. Persist settings through Tauri runtime storage later.
3. Keep macOS `@AppStorage` intact until the shared settings store exists.

Manual TODO:

- Audit old defaults before sharing settings across platforms.
- Avoid silently changing output behavior when settings migrate.

### File Import and Export Behavior

Sources:

- `StudioStore.chooseSourceFile`
- `StudioStore.accept`
- `StudioStore.convert`
- `StudioStore.openOutput`
- `desktop/full_spectrum_studio.py`

Current behavior:

- Source input: `.3mf`, `.obj`, `.glb`.
- Reference input: `.obj`, `.glb`, images.
- Texture override: PNG/JPEG for OBJ.
- Custom palette: JSON.
- Output opens in Bambu Studio or OrcaSlicer.

Extraction approach:

1. Tauri should use native dialogs via Tauri plugins.
2. Rust should scan selected folders/files and return metadata.
3. Engine execution should remain through Python until Rust parity tests exist.
4. Output handoff should be a Rust command with OS-specific launcher paths.

Manual TODO:

- Recreate macOS security-scoped resource behavior on Windows as explicit
  path permissions and runtime state.
- Keep original files untouched.

### Runtime State

Sources:

- `StudioStore`
- `ConverterService`

Reusable state:

- selected source
- selected reference/texture/custom palette
- inspection
- result
- progress
- progress message
- cancellable task ids
- preview asset URLs
- output preview URLs
- error message

Extraction approach:

1. Put long-running work state behind Rust commands/events.
2. React should render state, not own conversion correctness.
3. Keep generation ids/cancellation semantics from Swift to prevent stale
   results replacing current selections.

Manual TODO:

- Add Tauri event streaming for conversion progress.
- Add cancellation command before wiring conversion.

### Logging and Errors

Sources:

- `ConverterError`
- `ProcessDiagnostics`
- `StudioStore.errorMessage`
- Python progress JSON on stderr

Extraction approach:

1. Rust writes runtime logs in the app data log directory.
2. React reads recent logs through Rust.
3. Engine progress events should become Tauri events later.
4. Human-facing errors should remain concise; detailed logs stay on disk.

Manual TODO:

- Preserve the Python engine’s final error extraction.
- Add privacy filtering before logs include file/report details.

## Extraction Milestones

1. **Shared Models**
   Add TypeScript and Rust equivalents for project metadata, asset metadata,
   renderer state, runtime status and app settings.

2. **Runtime Shell**
   Wire native directory/file selection, metadata scanning and logs.

3. **Engine Bridge**
   Call `fullspectrum_engine.py --inspect --json` and convert the response to
   shared `ProjectInspection`.

4. **Progress Bridge**
   Convert Python progress lines into Tauri events and React status updates.

5. **Renderer Asset Contract**
   Render preview asset metadata first; add GPU rendering later.

6. **Validation Parity**
   Ensure Windows/Tauri output validation reports match macOS/Python behavior.

7. **Native Renderer**
   Introduce `wgpu` behind the `wgpu-runtime` feature only after the renderer
   contract and memory limits are stable.
