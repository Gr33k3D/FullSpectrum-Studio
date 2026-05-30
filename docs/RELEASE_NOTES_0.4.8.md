# FullSpectrum Studio 0.4.8 Community Preview

## Reliability and Diagnostics

Version 0.4.8 focuses on the tester reports from v0.4.6/v0.4.7 where some
painted `.3mf` files appeared to freeze and eventually showed an unhelpful
`none` error.

- The macOS app now reads both stdout and stderr from the Python conversion
  engine while it runs. Large final JSON results no longer block the child
  process before the app can decode them.
- Failed conversions show the real Python exception or JSON decode issue
  instead of a generic failure.
- Failed macOS conversions write a local debug log under
  `~/Library/Logs/FullSpectrumStudio/`.
- The error alert can copy a complete error report and open the debug log.
- The shared Python engine now prints a full traceback for command-line,
  macOS-app and Windows-desktop failures.
- The Windows desktop shell now shows tracebacks in its output panel, writes a
  local debug log and can copy the error report.
- Custom palette JSON parse errors include the file position that failed.

## Conversion Control

- Conversion and preview work can be cancelled from visible UI controls.
- Cancelling a macOS conversion terminates the active child Python process and
  escalates to a hard kill if the process does not exit promptly.
- Long-running work now shows heartbeat status. After a quiet period it says
  the engine is still working; after a longer quiet period it warns that the
  operation may be stuck and can be cancelled.
- A failed conversion cancels pending output-preview work so the app does not
  continue building a preview from a failed result.

## UI Fixes

- Browse/action button labels stay readable on hover/press in the Windows
  desktop shell and macOS app.
- macOS menu pickers visibly show the selected filament source, physical slot
  count and handoff destination.
- Status and progress text wraps instead of clipping awkwardly.
- Error messages are selectable/copyable and kept readable.
- Choosing a custom JSON palette from the macOS conversion prompt resumes the
  conversion instead of requiring a second start attempt.

## Honest Scope

FullSpectrum reduces and remaps existing Bambu paint states in a painted `.3mf`.
It does not repaint the model, smooth noisy painted regions or clean up a bad
source paint job. Very complex/noisy painted files can still be hard cases; the
new build should fail with useful diagnostics instead of silently hanging or
showing `none`.

## Verification

- Python engine tests include regressions for custom JSON parse diagnostics and
  command-line traceback output.
- The macOS Swift package builds in release mode.
- The release app bundle path is still produced by `script/build_and_run.sh`.
