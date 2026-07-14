# FullSpectrum Studio v0.4.16 Official Release

Version 0.4.16 fixes a Bambu Studio import failure affecting newer H2C project
files when FullSpectrum changes their filament count.

## H2C Vector Compatibility

Newer H2C projects can store several filament settings as three values per
filament. FullSpectrum previously recognized one-, two- and four-value layouts,
so the three-value arrays were left at the source filament count while the rest
of the project moved to the new count. Bambu Studio then reported `vector` and
followed it with a missing geometry warning.

FullSpectrum now recognizes and remaps the complete three-value blocks. This
keeps every filament-related vector aligned with the exported filament list.

## Validation

- 59 automated engine and desktop tests pass.
- A five-to-six-filament H2C regression verifies every three-value setting
  block is expanded to the correct length and keeps its slot grouping.
- The reported H2C project reopens and slices in Bambu Studio with intact
  geometry, five physical filaments, one logical mixed slot and preserved eye
  details.
- No submitted model, filename, inventory export, local path, private log,
  account detail or screenshot is included in the release.
