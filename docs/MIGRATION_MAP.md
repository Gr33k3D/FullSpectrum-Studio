# Migration Map

This map records how the current FullSpectrum Studio codebase should move from
a macOS-centric SwiftUI app plus Python engine toward shared desktop runtime
layers.

## Existing macOS Modules

| Area | Current Location | Notes |
| --- | --- | --- |
| App entry | `Sources/FullSpectrumStudio/App/FullSpectrumStudioApp.swift` | macOS app/window/commands. Keep platform-specific. |
| Main layout | `Sources/FullSpectrumStudio/Views/ContentView.swift` | UX reference for the Tauri layout. |
| Preview renderer | `Sources/FullSpectrumStudio/Views/InteractiveModelView.swift` | SceneKit-specific. Do not port directly to Windows. |
| UI controls | `Sources/FullSpectrumStudio/Views/*Card.swift` | Should inform React component shape, not be mechanically copied. |
| UI state | `Sources/FullSpectrumStudio/Stores/StudioStore.swift` | Contains reusable state transitions mixed with macOS file panels. Needs review before extraction. |
| Engine bridge | `Sources/FullSpectrumStudio/Services/ConverterService.swift` | Good model for a future Rust process bridge. |
| DTOs | `Sources/FullSpectrumStudio/Models/StudioModels.swift` | Best first candidate for shared JSON contract documentation. |
| Python engine | `fullspectrum_engine.py` | Current source of truth for conversion, validation and preview asset generation. |
| Bambu mixer model | `bambu_mixer_model.py` | Keep as shared color prediction logic until ported/tested. |
| Legacy Windows shell | `desktop/full_spectrum_studio.py` | Functional fallback; should be replaced only after Tauri reaches parity. |
| Old Windows installer | `packaging/windows/FullSpectrumStudio.iss` | Leave intact while Tauri packaging matures. |

## Proposed Shared Core Modules

| Proposed Module | Responsibility | First Consumer |
| --- | --- | --- |
| `core/project-loader` | Inspect `.3mf`, `.obj`, `.glb`, textures and metadata. | Tauri Rust command calling current Python engine first. |
| `core/color-engine` | Palette extraction, anchor selection, Delta E scoring and mix selection. | Python engine, then Rust or shared library. |
| `core/paint-engine` | Decode/remap Bambu paint states without formula guessing. | Existing Python validation path. |
| `core/validation` | Array/schema/paint/texture/reopened output validation. | Python engine, then Rust wrapper. |
| `runtime/filesystem` | App data/cache/log/output/project paths. | Tauri Rust backend. |
| `runtime/process` | Execute conversion jobs, progress events, cancellation. | Tauri Rust backend. |
| `renderer/contracts` | Preview asset metadata and render modes. | React shell before wgpu. |
| `renderer/wgpu` | Native GPU renderer once contracts are stable. | Future Tauri backend. |

## Move First

1. Define and document the JSON schemas currently implied by
   `StudioModels.swift`.
2. Make the Tauri Rust backend call `fullspectrum_engine.py --inspect --json`
   and return `ProjectInspection`.
3. Add conversion command that mirrors `ConverterService.convert(...)`.
4. Stream progress events from the Rust backend to React.
5. Share output/log/runtime paths between conversion and UI.

## Keep Platform-Specific

- SwiftUI app entry and `NSOpenPanel` usage.
- SceneKit view implementation.
- Tauri window configuration.
- Windows installer/bundling.
- macOS app bundle script and codesigning.
- Native “open in Bambu Studio / OrcaSlicer” launch paths.

## Requires Manual Review

- `StudioStore.swift`: useful behavior is mixed with AppKit/macOS assumptions.
- Large-model preview fallback: memory limits must match between shells.
- Inventory paths: Bambu Studio Beta paths differ by OS and install state.
- Launcher behavior: Windows installed app should not assume Python is present
  unless the engine is bundled or rewritten.
- Color preview parity: must keep one source of truth for predicted/exported
  mixed colors.

## Highest-Risk Areas

1. Paint remapping correctness. Any rewrite must keep decoded Bambu paint-state
   handling, not return to first-use or formula guessing.
2. Filament array alignment. The Tauri path must validate all arrays after
   writing and reopening the generated `.3mf`.
3. Large assets. Preview should degrade visualization quality before exhausting
   memory.
4. Renderer parity. The Windows renderer should not visually imply precision it
   does not have yet.
5. Packaging. The Windows app must either bundle the conversion engine or use a
   native Rust port; relying on a user-installed Python is not release quality.
