# FullSpectrum Studio v0.4.15 Official Release

Version 0.4.15 corrects filament profile metadata and prevents Auto from
expanding small projects to more physical filaments than they started with.

## Printer-Matched Filament Data

Inventory and catalog planning no longer carry a hardcoded H2C filament preset
into every output. FullSpectrum now uses neutral Bambu base profiles while
planning and binds each exported built-in filament to the printer profile
already stored in the source project. An A1 project therefore receives A1
filament presets instead of H2C preset IDs or Bambu Studio fallback badges.

## Physical Slot Limit

When a project has six or fewer active source colors, Auto keeps that same
physical filament count. Automatic reduction begins when the source exceeds
the six-slot automatic limit. A manual physical-slot choice remains an
explicit override.

The reported five-color rooster project now uses five physical filaments plus
one logical mixed slot. The mixed slot combines two of those physical
filaments; it is not a sixth spool. Black and white remain exact, estimated
mean Delta E is 1.33 and maximum Delta E is 2.70.

## Validation

- 58 automated engine and desktop tests pass.
- The generated A1 project contains only A1-compatible built-in preset IDs.
- The reported project reopened in Bambu Studio with five physical filaments,
  one mixed slot, intact geometry and black eye details.
- No user model, inventory export, local path, private log or screenshot is
  included in the release.
