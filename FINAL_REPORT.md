# FullSpectrum Studio v0.4.3 Final Report

## Ship Decision

Version `0.4.3-community-preview` is the release candidate. It keeps the
project's narrow purpose:

```text
painted project -> palette reduction -> filament planning
-> mixed filament generation -> validated .3mf
```

It is not a slicer, and the preview is not a calibrated claim about a finished
print.

## Critical Color Fix

The real angel source project contains purple painted targets, including
`#553B6A`, `#882FAA` and `#937EA6`. The earlier UI made this confusing by
showing target swatches in the mixed-recipe list, while its prediction math
could disagree with the color Bambu Studio loaded.

Version 0.4.3 now:

- Uses Bambu Studio `FilamentMixer` loaded-swatch reconstruction for planning,
  exported colors and preview.
- Shows the painted target and reconstructed exported output separately.
- Reopens every output and rejects any mixed slot whose saved display color is
  not the color Bambu reconstructs from its serialized components and ratios.
- Emits a mixed slot only when its reconstructed output is within Delta E `8`
  of the painted target. A poor match stays visible as an unmatched physical
  fallback warning instead of becoming a misleading recipe.

## Real Project Validation

One local painted angel `.3mf` with a GLB visual reference was converted in
owned-filament mode using six physical slots. The private model and inventory
are not distributed.

| Check | Result |
| --- | --- |
| Source mesh size | `5,417,070` triangles |
| Output palette | `6` physical + `11` mixed slots |
| Written archive reopen/schema/paint/resource validation | Passed |
| Bambu loaded-swatch synchronization | Passed, maximum Delta E `0.00` |
| Largest accepted mixed-target error | Delta E `7.70` |
| Unmatched painted colors | `6`, explicitly warned and not represented as bad mixes |
| Estimated mean error | Delta E `3.73` |
| Estimated quality / reference similarity | `91.8 / 100` / `86.4 / 100` |
| Contrast retention / confidence | `81.0%` / `79.6` (`High`) |
| Wall time / peak resident memory | `66.37 s` / `100.3 MB` |

These are planning and software-consistency results. Physical output still
depends on loaded filament, printing conditions, illumination and calibration.

## Viewer And Performance

- The macOS viewer is now the primary workspace, with collapsible tools and
  activity log plus fullscreen display.
- The original plate render plus original 3D, reduced/predicted, validation,
  heatmap, anchor-influence and wireframe views are available from the same
  result.
- For the `5.4` million-triangle local project the viewer automatically built
  shape-preserving bounded display proxies rather than presenting an empty or
  fragmented viewport. The two analysis OBJ overlays each contained `71,389`
  display faces and were about `2.3 MB`.
- The predicted result reuses validated analysis geometry with its output
  materials, avoiding a second expensive large-mesh viewport pass after
  conversion.
- The optimized preview affects visualization only. Conversion, paint remap,
  array checks, texture/UV/resource checks and archive reopening still operate
  on the complete project.

## Supported And Experimental

Supported:

- Painted Bambu Studio `.3mf` conversion to a separate validated output.
- Local read-only Bambu Studio inventory, Bambu planning palettes, exact
  CMYKW roles and local custom filament libraries.
- Optional OBJ, GLB or image reference scoring.
- macOS desktop application and shared-engine Windows packaging workflow.
- Validated-output handoff to an installed Bambu Studio or OrcaSlicer app.

Experimental:

- Textured OBJ source import with complete UVs and a PNG/JPEG texture.
- Constrained embedded-texture GLB source import.

Not claimed:

- Printer-calibrated color prediction.
- Exact time, material, swap or purge-use estimates before slicing.
- Universal GLB conversion or raw imports over the face-count safety limit.
- A native OrcaSlicer plugin or Orca-specific mixed-color validation.

## Verification

- `28` automated conversion, paint-code, Bambu-color, import, archive-safety,
  resource-fallback and privacy regression tests pass.
- The release macOS application builds and launches successfully; the assembled
  bundle and an extracted release ZIP pass strict `codesign` verification.
- The macOS download is ad-hoc signed rather than Developer ID notarized;
  Gatekeeper trust is not claimed for this community preview.
- Generated shareable text reports omit local reference filenames and
  inventory quantities.
- Release packaging includes the PolyForm Noncommercial 1.0.0 license and the
  MIT third-party notice for the Bambu-compatible mixer reconstruction.

## Recommended v0.5 Direction

Do not expand source formats first. The responsible next improvement is an
optional local calibration-card workflow for a user's real filaments, followed
by importing slicer-produced time, purge and material statistics. Those steps
would improve real print decisions without changing FullSpectrum's identity.
