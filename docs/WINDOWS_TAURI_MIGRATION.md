# Windows Tauri Migration

FullSpectrum Studio now has a side-by-side Windows desktop foundation in
`apps/windows-tauri/`. The existing macOS SwiftUI application is preserved in
`Sources/FullSpectrumStudio` and remains the production community-preview app
until the new runtime and renderer layers are migrated.

## What Was Added

- Tauri v2 desktop shell.
- React + TypeScript + Vite frontend.
- Rust backend bridge with structured commands.
- Windows runtime directory preparation.
- Native folder picker through the Tauri dialog plugin.
- Native source/reference/output pickers.
- FullSpectrum engine inspection and conversion commands.
- Three.js GLB/OBJ orbit viewer with a build plate scale reference.
- Basic project/workspace metadata scanning in Rust.
- Runtime log writes and recent-log reads through Rust commands.
- Output reveal/open-folder command.
- Renderer abstraction placeholders in TypeScript.
- GPU/runtime placeholder module in Rust with a future `wgpu-runtime` feature.
- MSI-oriented Tauri bundle configuration.
- Separate GitHub Actions workflow for Windows Tauri builds.

## Run the Windows/Tauri App

From the repository root:

```bash
cd apps/windows-tauri
npm install
npm run tauri:dev
```

For frontend-only development:

```bash
cd apps/windows-tauri
npm install
npm run dev
```

## Build the Installer

On Windows:

```bash
cd apps/windows-tauri
npm ci
npm run typecheck
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:build
```

The Tauri bundle target is currently configured for MSI output. CI uploads
installer/build artifacts from:

```text
apps/windows-tauri/src-tauri/target/release/bundle/msi/
apps/windows-tauri/src-tauri/target/release/*.exe
```

## Current Limitations

- The renderer is not the macOS SceneKit viewer yet. The Tauri app displays the
  available source plate thumbnail and can orbit GLB/OBJ reference models with
  a 256 mm build plate scale reference, but native 3MF preview meshes, heatmaps
  and anchor influence still need the shared renderer layer.
- The Rust backend now launches the existing Python engine for inspection and
  conversion. This keeps behavior aligned with the stable engine while the core
  is extracted.
- Project folder scanning is intentionally shallow and bounded. It reports file
  counts, supported asset counts and a small asset list, but does not parse
  Bambu `Metadata/project_settings.config` yet.
- GPU probing is intentionally a placeholder. `wgpu` is not pulled into the
  default build.
- The old PyInstaller Windows shell remains in `desktop/` and
  `packaging/windows/`. It is not removed by this migration.

## Migration Phases

1. **Runtime Bridge**
   Move process launching, runtime paths, logs, project selection and output
   discovery behind Rust commands. Keep conversion behavior delegated to the
   existing Python engine until the core is extracted.

2. **Project Loader Contract**
   Extract 3MF/OBJ/GLB metadata inspection into a stable JSON contract shared by
   SwiftUI, Tauri and tests. The first Rust command should call the existing
   engine CLI and return the same metadata shape as `ProjectInspection`.

3. **Renderer Contract**
   Define shared preview asset records for:
   - original preview
   - predicted preview
   - heatmap
   - anchor influence
   - wireframe metadata

   React should consume this contract before native GPU rendering is added.

4. **wgpu Renderer**
   Enable the `wgpu-runtime` feature only after the renderer bridge has stable
   ownership, cancellation and memory limits. The future Rust renderer should
   own adapter selection and expose bounded render state to React.

5. **Engine Extraction**
   Extract reusable color, paint mapping, validation and packaging logic from
   `fullspectrum_engine.py` into a platform-neutral core. Do this after the
   Tauri shell can call and validate the existing engine.

## Swift/Metal to Tauri/Rust/wgpu Strategy

The macOS app currently uses SwiftUI and SceneKit for the interactive preview.
The Windows migration should not try to port SceneKit. Instead:

- Keep SwiftUI/SceneKit as the macOS shell and proven UX reference.
- Extract preview asset generation before renderer code.
- Use React for layout/state.
- Use Three.js for the current portable GLB/OBJ reference viewer.
- Use Rust commands for filesystem/runtime/work orchestration.
- Add `wgpu` only behind a feature flag after the preview contract is stable.
- Keep large-model fallback behavior and memory limits explicit in both shells.

## CI

The workflow `.github/workflows/windows-tauri.yml` runs on Windows and:

- installs Node
- installs Rust stable
- installs frontend dependencies
- runs TypeScript typecheck
- builds the Vite frontend
- runs `cargo check`
- builds the Tauri MSI bundle
- uploads build artifacts

The existing release workflow is left untouched.
