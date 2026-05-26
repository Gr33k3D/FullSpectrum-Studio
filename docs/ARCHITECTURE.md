# Architecture

## Pipeline

1. The desktop app selects a painted Bambu `.3mf` and optional reference.
2. The Python engine safely extracts the ZIP container and reads
   `Metadata/project_settings.config` plus every `3D/Objects/*.model`.
3. `paint_color` facet states are decoded as Bambu TriangleSelector serialized
   states. Embedded slot numbers are remapped to the selected reduced palette.
4. Physical slots are selected from the requested filament source. Mixed slots
   are generated only from physical slots and are appended after them.
5. Project filament arrays and purge matrices are resized through their
   detected slot/matrix layout.
6. The output archive is written separately, reopened, structurally validated,
   and compared to preservation hashes from the source.
7. Recipes, estimated quality and a human-readable report are returned to the UI.

## Components

- `fullspectrum_engine.py`: conversion, codec, reference analysis and validation.
- `Sources/FullSpectrumStudio`: native macOS SwiftUI shell and SceneKit preview.
- `desktop/full_spectrum_studio.py`: Windows/cross-platform desktop shell for the same engine.
- `tests/test_engine.py`: regression and security tests using synthetic projects only.

## Paint Mapping

Bambu paint values are not filament labels in encounter order. For example,
leaf states observed in an original project include `8`, `0C`, `1C`, `2C`,
`DC` and extended states such as `1FC`. The engine parses the serialized state
tree, replaces only its embedded nonzero extruder slots, and re-encodes it.
No first-use lookup or formula guess is used.

## Reference Inputs

GLB reference handling reads the glTF header and embedded texture buffer view
under size limits. OBJ mode resolves a referenced material texture when
present. Texture sampling is local and produces only dominant-color summaries
and an estimated score. Printable geometry continues to come from the `.3mf`.
