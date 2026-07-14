# Changelog

## 0.4.16 Official Release - 2026-07-14

### Fixed

- Resizes the three-value-per-filament setting arrays written by newer H2C
  project files when FullSpectrum changes the output filament count.
- Prevents Bambu Studio's `vector` import error and the follow-on missing
  geometry warning for those projects.

### Validation

- Adds a regression for growing a five-filament H2C project to five physical
  filaments plus one logical mixed slot.
- Reopens and slices the reported H2C project in Bambu Studio with intact
  geometry, five physical filaments, one mixed slot and preserved eye details.

## 0.4.15 Official Release - 2026-07-14

### Fixed

- Rebinds built-in filament presets to the printer profile already stored in
  the source project instead of exporting H2C-specific preset IDs into A1 and
  other printer projects.
- Uses neutral Bambu base presets while planning, removing device-specific
  profile defaults from inventory and catalog data.
- Stops Auto from increasing the physical filament count when a project has
  six or fewer active source colors. Manual physical-slot choices still act as
  explicit overrides.
- Keeps small black and white details while respecting that physical-slot
  limit; mixed colors remain separate logical slots and do not require another
  physical spool.

### Validation

- Adds an end-to-end A1 preset regression and strengthens the five-color
  small-detail planner regression.
- Reopens the reported five-color project in Bambu Studio with five physical
  filaments, one mixed slot, correct A1 presets and intact geometry.

## 0.4.14 Official Release - 2026-07-14

### Fixed

- Makes worst-case visible color error count more strongly during automatic
  anchor selection, preserving small black, white and other high-contrast
  details instead of letting large painted regions dominate the plan.
- Caps the displayed quality score by the largest visible color error so a
  plan with one badly shifted detail is no longer reported as high quality.
- Includes object- and part-level filament assignments in planning even when
  those regions do not contain explicit painted facets.
- Stops unused source colors from creating unused mixed-recipe slots.

### Compatibility And Privacy

- Adds regression coverage for H2C two-nozzle slot arrays and for a second
  conversion after adding or repainting a physical color.
- Keeps Bambu's valid automatic object-filament assignment at slot zero.
- Updates Windows packaging to Pillow `12.3.0`, which fixes the vulnerabilities
  disclosed against `12.2.0`, and runs `pip-audit` in the release workflow.
- Reopens and verifies the packaged macOS ZIP so release validation covers the
  distributable archive as well as the working app bundle.
- Makes copied macOS and Windows error reports privacy-safe by excluding local
  paths, model names, inventory data and raw engine output. Detailed logs stay
  local and are labeled private.
- Shows both mean and maximum estimated color error in macOS and Windows plan
  results.

## 0.4.13 Official Release - 2026-07-13

### Desktop Apps

- Reworks the macOS app into a preview-first workspace with separate Plan,
  Filaments and Results inspectors.
- Adds Preview Plan to the Windows app and shows the release version in its
  title bar and header.
- Moves both desktop packages and engine output filenames to one shared
  `VERSION` file.

### Fixed

- Preserves eight-digit Bambu filament colors such as `#00000000` instead of
  dropping the slot and shifting every later paint reference.
- Opens the Results inspector when a macOS plan preview completes.
- Clears stale validation results when planner inputs change or a new run
  begins.
- Keeps manually pinned anchors when the filament search field hides them and
  prevents selecting more pins than the physical-slot limit.

### Release And Privacy

- Adds Windows shell compile/import checks to the release workflow, pip
  caching, scoped permissions and concurrency control.
- Updates Windows packaging to Pillow `12.2.0` and PyInstaller `6.21.0`; the
  pinned direct dependencies pass `pip-audit` with no known vulnerabilities.
- Removes private-model screenshots, names and local machine paths from the
  current public tree.

## 0.4.9 Official Release - 2026-05-31

### Release

- Promotes the v0.4.8 reliability work into an official macOS and Windows
  release path instead of a community-preview-only package.
- Keeps smart quality mode enabled by default so FullSpectrum tests practical,
  balanced, detail and high-detail plans, then selects the best validated
  palette for the model's painted usage.
- Improves physical anchor selection by scoring final palettes after mixed
  recipes are generated, which helps choose parent colors that actually produce
  better reconstructed Bambu swatches.
- Adds a catalog-region selector for Bambu planning colors on macOS and
  Windows, and carries the selected region into warnings, JSON output and the
  shareable report.
- Keeps the catalog promise honest: the region is planning metadata only, and
  FullSpectrum still does not check live Bambu store stock.
- Updates the GitHub release workflow so plain tags such as `v0.4.9` create an
  official latest release, while `*-community-preview` tags remain prereleases.

## 0.4.8 Community Preview - 2026-05-30

### Reliability

- Drains conversion engine stdout and stderr continuously from the macOS app so
  large JSON conversion results cannot fill the pipe and stall the Python child
  process before exit.
- Surfaces real engine exceptions, tracebacks and JSON decode failures instead
  of falling back to vague messages such as `none`.
- Writes local conversion debug logs for failed macOS conversions and adds a
  copyable error report.
- Shows Windows desktop-shell tracebacks in the output panel, writes a local
  debug log and adds a copy error report action.
- Adds progress heartbeat text for long-running conversions and possible
  stalls, plus a Cancel/Stop control that terminates the active macOS Python
  conversion process.

### User Interface

- Keeps browse/action button text and selected picker values readable in dark
  mode on macOS and in the Windows desktop shell.
- Makes custom JSON palette selection resume the conversion that asked for it.
- States in the UI and docs that FullSpectrum remaps existing Bambu paint
  states; it does not repaint, smooth or clean up a badly painted source model.

## 0.4.3 Community Preview - 2026-05-27

### Critical Fix

- Replaces FullSpectrum's independent mixed-swatch preview calculation with
  Bambu Studio compatible `FilamentMixer` reconstruction.
- Scores candidate mixes from the serialized, rounded component ratios Bambu
  actually reloads and displays.
- Reopens each written archive and rejects it if `filament_colour`,
  `filament_multi_colour` or any reconstructed mixed swatch is inconsistent.
- Adds Validation preview mode, Color Debug View and a generated
  `*_COLOR_VALIDATION.md` report.
- Adds regression coverage for purple, green, orange, neutral and dark mixes,
  plus Bambu-loaded mixed swatches from the local angel benchmark.
- Stops creating a mixed logical slot when Bambu reconstruction remains more
  than Delta E `8` from the painted target, and reports unmatched painted
  colors as a request for closer physical filament choices.
- Distinguishes painted target swatches from actual reconstructed output
  swatches in the recipe list.

### Viewer And Reliability

- Makes the orbitable viewer the main workspace, with collapsible controls,
  collapsible activity output and fullscreen viewing.
- Keeps the detailed original plate render selectable alongside the bounded
  orbitable 3D view for exceptionally complex projects.
- Replaces the large-model blank-preview path with a full-surface,
  grid-reduced optimized preview and matching heatmap/anchor overlays.
- Makes compact-height windows scroll cleanly instead of allowing the viewer,
  log and controls to collide.
- Makes Finder reveal fall back to opening the output directory if selecting
  the generated file is unavailable.
- Resolves inventory colors to installed Bambu catalog names where the Beta
  inventory supplies only a color code, with honest hexadecimal fallback.
- Removes inventory quantities from generated shareable text reports and
  covers that privacy boundary with a regression test.
- Adds a validated-output destination choice for installed Bambu Studio or
  OrcaSlicer; Orca support is an explicit file handoff rather than a claimed
  plugin.
- Rebuilds release packaging from source on macOS and Windows, and seals and
  strictly verifies the assembled ad-hoc signed macOS bundle before ZIP
  packaging.

## 0.4.2 Community Preview - 2026-05-27

### Fixed

- Replaces stacked SwiftUI file-import presentations with a reliable native
  macOS file panel for source, reference, OBJ texture and custom-library
  selection.
- Makes `Compose Palette` open the correct native chooser when a required
  source or custom filament library has not yet been selected.
- Provides immediate status feedback while a file chooser is open and restores
  the previous status if selection is cancelled.

## 0.4.1 Community Preview - 2026-05-27

### Fixed

- Opens painted `.3mf` files through a fast metadata and thumbnail path before
  optional interactive rendering work begins.
- Skips automatic interactive/analysis mesh generation above `750,000`
  triangles, preserving conversion and validation without an avoidable memory
  spike.
- Keeps modest textured OBJ/GLB sources visible while paint analysis runs in
  the background.
- Prevents cancelled or older source/output preview tasks from restoring the
  previous model after a new selection.
- Retains macOS read permission for the selected source and scopes optional
  texture/reference/library access only to the work that needs it.

## 0.4.0 Community Preview - 2026-05-27

### Changed

- Uses CIEDE2000 for palette scoring and reports estimated confidence,
  brightness preservation and contrast retention.
- Adds quality-versus-waste planning, visual-gain gating for mixed slots and
  reuse of identical mixed recipes.
- Validates the exact decoded paint-state remap after reopening every written
  `.3mf`.
- Adds reduced/predicted, heatmap, anchor-influence and wireframe views in the
  macOS application, with model/load statistics and render presets.
- Adds experimental constrained textured OBJ and embedded-texture GLB import,
  routed through the same validator as painted `.3mf` conversion.
- Makes Windows controls and output reporting follow the shared v0.4 engine.

### Stabilized

- Streams imported OBJ model XML and stores sampled image pixels compactly to
  reduce peak memory for large textured inputs.
- Rejects GLB sources declaring more than two million faces before loading
  their binary geometry payload.
- Generates analysis overlays from one reduced viewport geometry pass.
- Makes cancellation, session replacement and Finder/Explorer output reveal
  predictable.
- Removes local reference filenames and inventory paths from generated
  shareable reports.

### Compatibility

- Existing painted `.3mf` input remains the supported primary workflow.
- Textured OBJ/GLB source import is experimental and rejects unsupported
  texture, primitive, UV or size cases explicitly.
- Outputs remain separate files; source projects are not overwritten.

## 0.3.0 Community Preview - 2026-05-26

- First public preview with decoded Bambu paint remapping, physical/mixed slot
  validation, local reference scoring, macOS viewer and Windows packaging.
