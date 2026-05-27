# Architecture

## Pipeline

1. The desktop app selects a painted Bambu `.3mf`, or experimentally a
   constrained textured `.obj`/`.glb`, plus an optional visual reference.
2. The Python engine safely extracts the ZIP container and reads
   `Metadata/project_settings.config` plus every `3D/Objects/*.model`.
3. `paint_color` facet states are decoded as Bambu TriangleSelector serialized
   states. Embedded slot numbers are remapped to the selected reduced palette.
4. CIEDE2000-weighted anchor selection uses painted usage and, when supplied,
   a modest texture-reference contribution. Physical slots are selected from
   the requested filament source.
5. Mixed slots are generated only from physical slots, only when predicted
   visual gain clears the selected quality-versus-waste threshold, and are
   reused when two paint targets share the same printable recipe.
6. Project filament arrays and purge matrices are resized through their
   detected slot/matrix layout.
7. The output archive is written separately, reopened, structurally validated,
   compared to preservation hashes, and checked against the exact expected
   decoded paint remap.
8. Recipes, confidence/contrast/complexity estimates and optional analysis
   meshes are returned to the UI.

Heatmap and anchor-influence display assets share one reduced viewport geometry
pass and differ only in material colors; large converted archives are not
decompressed twice merely to draw two overlays.

Since v0.4.1, opening a `.3mf` reads its palette and thumbnail before optional
interactive work. Interactive and analysis viewport meshes are omitted above
`750,000` triangles, leaving conversion/validation available without committing
the application to a disproportionate display allocation. Background preview
results are generation-scoped, so an older file cannot replace a newer
selection when it finishes later.

## Components

- `fullspectrum_engine.py`: conversion, codec, reference analysis and validation.
- `Sources/FullSpectrumStudio`: native macOS SwiftUI shell and SceneKit preview.
- `desktop/full_spectrum_studio.py`: Windows/cross-platform desktop shell for the same engine.
- `tests/test_engine.py`: regression and security tests using synthetic projects only.
- `tools/benchmark_quality.py`: private-local comparison of practical,
  balanced and detail planning settings.

## Paint Mapping

Bambu paint values are not filament labels in encounter order. For example,
leaf states observed in an original project include `8`, `0C`, `1C`, `2C`,
`DC` and extended states such as `1FC`. The engine parses the serialized state
tree, replaces only its embedded nonzero extruder slots, and re-encodes it.
No first-use lookup or formula guess is used.

## Reference Inputs

GLB reference handling reads the glTF header and embedded texture buffer view
under size limits. Reference-only OBJ resolves its material texture. Texture
sampling is local and produces only dominant-color summaries and an estimated
score.

Experimental OBJ import parses triangle geometry and complete UV references,
samples its linked or explicitly selected PNG/JPEG base-color texture, clusters colors deterministically, embeds the
texture and UV mapping in an intermediate painted 3MF, and then invokes the
normal validated converter. Experimental GLB import applies node transforms and
accepts only uncompressed triangle primitives with positions, UVs and one
embedded texture. Both warn when extended analysis colors must be compressed to
the Bambu paint-slot limit; unsupported GLB material/compression cases fail
explicitly, as do imports above the two-million-face safety limit.
