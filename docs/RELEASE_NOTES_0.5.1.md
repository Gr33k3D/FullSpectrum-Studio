# FullSpectrum Studio v0.5.1 Official Release

Version 0.5.1 fixes inventory selection, adds direct control over available
filament colors, and removes repeated large-model work from forecasts and
conversion.

## Inventory Fix

FullSpectrum could read an older Bambu Studio Beta inventory when both the Beta
and main Bambu Studio profiles existed. A spool recently added to the main
Filament Manager was then missing from My Inventory planning even though Bambu
Studio showed it correctly.

The app now selects the inventory file updated most recently, with the main
Bambu Studio profile winning a timestamp tie. The inventory screen also opens
when fewer than two colors are active; conversion reports the physical-color
requirement when a plan is attempted.

## Filament Color Selection

The macOS and Windows apps now show the colors available to the current
filament source before planning. Owned colors include their combined remaining
grams.

Each color has two independent controls:

- Enabled colors may be selected automatically by the planner.
- Pinned colors must occupy a physical filament slot.

At least two distinct colors must remain enabled. A pinned color is enabled
automatically, and disabled colors are excluded from owned-filament guidance.

## Faster Large-Model Work

The first 3D preview builds one bounded display mesh. FullSpectrum now reuses
that mesh for render-weighted planning, predicted color previews, color-loss
heatmaps and anchor-influence views. Plan-only forecasts read settings and
paint states directly from the 3MF instead of extracting and fingerprinting the
whole archive.

Common Bambu mixer results and color distances are cached without changing the
recipe search or reconstructed swatches. Preview resolution, source paint
mapping and final validation are unchanged.

On the local 84 MB verification project with 5.4 million triangles:

- A Best/Smart forecast after preview creation fell from about 77 seconds to
  15 seconds.
- A complete cached conversion, archive rewrite, reopen and validation took
  about 27 seconds.

The source project used for this check is private and is not part of the
release.

## Validation And Privacy

- All 65 engine and desktop regression tests pass.
- The optimized preview is byte-for-byte equivalent apart from its local
  material-library filename.
- Bambu mixed-color reconstruction regressions retain the same expected
  swatches.
- The release contains no submitted model, model filename, local path,
  inventory record, spool quantity, account detail or private log.
