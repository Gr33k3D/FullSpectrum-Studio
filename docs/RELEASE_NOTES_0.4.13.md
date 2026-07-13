# FullSpectrum Studio v0.4.13 Official Release

Version 0.4.13 brings the current macOS work back into one cross-platform
release. It also fixes a palette parser error found in a real 32-slot project.

## Fixed

Bambu projects can store a filament color with eight hex digits. One observed
project used `#00000000` in slot 1. FullSpectrum accepted only six-digit values,
so it dropped that entry, treated the 32-slot palette as 31 slots and rejected
a valid slot 32 paint state. The parser now accepts six- and eight-digit Bambu
colors while preserving every slot position. Invalid values report their slot
number instead of shifting the palette.

The macOS app now clears old results when planning settings change or a new run
starts. A finished Preview Plan opens the Results inspector automatically.
Anchor searches no longer remove pins that happen to be hidden by the current
search text, and the UI stops users from pinning more physical colors than the
selected slot count allows.

## macOS

The main window now keeps the model preview as the primary workspace. Planning,
filament inventory and results use separate inspector tabs, with a compact
activity strip below the preview. Controls use a quieter neutral palette and
fit at the default and compact window sizes.

## Windows

The Windows shell now has a Preview Plan button. It runs the same local planner
without writing a 3MF, then lists physical and mixed slot counts, quality,
confidence, printability, anchors, recommendations and warnings. Planning can
use paint-state or render-preview weighting. The title bar and header show the
release version. Windows packaging now uses Pillow `12.2.0` and PyInstaller
`6.21.0`; the pinned direct dependencies pass `pip-audit` with no known
vulnerabilities.

## Privacy

This release contains no user model, inventory export, generated report, debug
log or local workspace note. Old private-model screenshots and machine-specific
paths were removed from the current tree. Generated files remain local unless
the user chooses to share them.

## Validation

- All `49` Python engine and desktop tests pass.
- The macOS Swift package builds in debug and release modes.
- The signed macOS app bundle passes strict verification.
- The Windows shell compiles and imports without opening a GUI.
- GitHub Actions builds the Windows portable ZIP and Inno Setup installer from
  the same tag used for the macOS package.
