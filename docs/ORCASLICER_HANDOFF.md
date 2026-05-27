# OrcaSlicer Handoff

FullSpectrum Studio is an external painted-project converter. It reduces a
palette, creates recipes and validates the new `.3mf` before any slicer is
opened.

Version 0.4.3 adds an output destination choice:

- `Bambu Studio`: open the validated project in Bambu Studio.
- `OrcaSlicer`: open the validated project in an installed OrcaSlicer app.

This is a deliberate file handoff, not an OrcaSlicer add-on or plugin. The
OrcaSlicer public project exposes normal project import/use as a slicer; this
release does not rely on an undocumented internal extension API.

## Compatibility Boundary

The mixed-color display reconstruction and reopen validator are based on the
Bambu Studio project behavior used by FullSpectrum outputs. OrcaSlicer can be
useful for opening and slicing the output, but the app does not claim that
Orca reconstructs every Bambu mixed-filament display color identically.

For an OrcaSlicer workflow:

1. Convert and validate in FullSpectrum Studio.
2. Select `OrcaSlicer` as the output destination or open the output manually.
3. Check assigned physical and mixed filament slots in OrcaSlicer.
4. Slice and use a small color test before a long color-sensitive print.

## Direction

If OrcaSlicer publishes a stable extension mechanism suitable for pre-slice
painted-project conversion, a native integration can be evaluated later.
Until then, a transparent validated-file handoff is faster for users and safer
than depending on undocumented behavior.

Official OrcaSlicer project:
[github.com/OrcaSlicer/OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer)
