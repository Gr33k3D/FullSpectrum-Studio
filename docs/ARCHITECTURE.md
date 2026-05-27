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
5. Mixed slots are generated only from physical slots. Candidate quality and
   exported swatches use Bambu Studio `FilamentMixer` reconstruction from the
   saved, percentage-rounded ratios; recipes are reused where possible. A
   candidate is emitted only if the reconstructed result is within Delta E
   `8` of its painted target, so an attractive target color cannot masquerade
   as a poor printable output.
6. Project filament arrays and purge matrices are resized through their
   detected slot/matrix layout.
7. The output archive is written separately, reopened, structurally validated,
   compared to preservation hashes, checked against the exact expected decoded
   paint remap, and rejected if Bambu's reconstructed mixed colors differ.
8. Recipes, confidence/contrast/complexity estimates and optional analysis
   meshes are returned to the UI.

Predicted, heatmap and anchor-influence display assets share one reduced
viewport geometry pass and differ only in material colors; large converted
archives are not decompressed again merely to change view mode.

Opening a `.3mf` reads its palette and thumbnail before optional interactive
work. Large projects are visualized with sampled, grid-reduced viewport meshes
and analysis overlays, while palette conversion and reopened-archive
validation continue to use the full project data. The UI tells the user when
the optimized preview is active. Background preview results are
generation-scoped, so an older file cannot replace a newer selection when it
finishes later.

The macOS shell opens source, reference, custom-library and OBJ-texture files
through one native `NSOpenPanel` path. This avoids competing view-level
presentation modifiers and makes every file-selection button perform the same
observable action.

## Components

- `fullspectrum_engine.py`: conversion, codec, reference analysis and validation.
- `bambu_mixer_model.py`: MIT-attributed Bambu mixed-filament display-color
  reconstruction shared by planning, export validation and preview.
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
