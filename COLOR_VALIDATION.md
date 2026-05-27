# Color Validation

## Why This Fix Exists

FullSpectrum previously predicted a mixed slot with its own perceptual color
blend and saved that swatch into the project. Bambu Studio does not simply keep
that swatch: when it loads a mixed filament, it reconstructs the visible color
from the physical component slots and `filament_mixed_sublayer_ratios`.

That could make a preview appear purple in FullSpectrum while Bambu displayed a
materially different blue/teal result for the exported recipe.

## Verified Bambu Behavior

Bambu Studio reads:

- `filament_colour`
- `filament_multi_colour`
- `filament_mixed_components`
- `filament_mixed_sublayer_ratios`

For mixed slots it turns the stored ratio values into integer percentages,
computes the display swatch through `blend_color_multi` / `FilamentMixer`, and
updates both color arrays in memory. This behavior is visible in the official
BambuStudio source:

- <https://github.com/bambulab/BambuStudio/blob/master/src/slic3r/GUI/Plater.cpp>
- <https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/FilamentMixer.cpp>
- <https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/FilamentMixerModel.hpp>

The included compatibility representation of `FilamentMixerModel.hpp` retains
its MIT attribution in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## v0.4.3 Rule

One color path is used for candidate selection, recipes, preview meshes and
export validation:

1. Serialize mixed ratios to the values written into the `.3mf`.
2. Apply Bambu's percentage loading behavior.
3. Reconstruct the Bambu mixed color.
4. Save that same color into both filament color arrays.
5. Reopen the written archive and reject it if reconstruction differs.

Every conversion also writes a `*_COLOR_VALIDATION.md` file listing target,
app/export color, Bambu-reconstructed color, recipe and Delta E values.

## Remaining Limitation

Matching Bambu Studio's loaded display color is not a laboratory prediction of
the physical print. Filament translucency, layer height, surface finish,
purging, illumination and calibration can still alter printed appearance.
