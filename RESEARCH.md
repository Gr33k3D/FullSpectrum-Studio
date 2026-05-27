# FullSpectrum Studio Research Notes

Research date: 27 May 2026

## Product Boundary

FullSpectrum Studio is not a general color-mixing slicer. Its job is:

```text
painted project -> palette reduction -> filament planning
                -> mixed-filament assignments -> validated Bambu .3mf
```

That boundary matters. A slicer can decide cadence, tool ordering and measured
printer-specific behavior at slicing time. FullSpectrum instead has to preserve
existing painted facet intent and produce a project that another slicer can
open safely.

## Reviewed Workflows

### Prusa ColorMix / EasyPrint

Prusa announced ColorMix for PrusaSlicer and EasyPrint on 26 May 2026. Its
official description treats alternating filament exposure as a spatial optical
mixing problem and uses printed/measured calibration rather than a naive RGB
average. The feature is integrated with slicing and is initially grounded in
Prusa's measured material and printer combinations.

Useful lesson for FullSpectrum: mixed colors should use small printable ratio
schedules, carry uncertainty, and be evaluated against the benefit they buy.

Not adopted: Prusa implementation, coefficients, measured color library, or
claims that Prusa calibration predicts Bambu/third-party filament appearance.

Source:

- [Prusa: Our new open-source ColorMix model in PrusaSlicer and EasyPrint](https://blog.prusa3d.com/our-new-open-source-colormix-model-in-prusaslicer-and-easyprint_136079/)

### Snapmaker Orca FullSpectrum

The public Snapmaker Orca FullSpectrum fork adds virtual mixed filaments to a
slicer for layer alternation, ratio control, preview and slicing behavior. Its
README also warns that project serialization has changed during development and
old mixed-filament projects may not migrate cleanly.

Useful lesson for FullSpectrum: virtual colors must be traceable back to
physical colors, and project serialization needs explicit validation and
compatibility testing.

Not adopted: slicer source, toolpath algorithms, Local-Z behavior or its
AGPL-governed implementation. FullSpectrum does not become a slicer fork.

Source:

- [ratdoux/OrcaSlicer-FullSpectrum README](https://github.com/ratdoux/OrcaSlicer-FullSpectrum)

### Bambu Studio Mixed-Filament Context

Bambu Studio's public source contains mixed-filament color prediction code and
project structures. FullSpectrum relies only on observed project structure and
its own paint-state decoder/validator; it does not embed Bambu color-prediction
source. Generated outputs are reopened and checked before being offered to the
user.

Source:

- [BambuStudio `FilamentMixerModel.hpp`](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/FilamentMixerModel.hpp)

## Color And Image Methods

- CIEDE2000 improves perceptual difference comparison over plain Euclidean
  CIELAB for color-pair evaluation. Version 0.4 implements CIEDE2000 and
  validates it against the published Sharma/Wu/Dalal reference pair.
- Weighted k-means is a useful, understandable quantizer for texture-derived
  colors. Version 0.4 uses deterministic CIELAB clustering for experimental
  constrained textured OBJ/GLB import.
- Spatial appearance matters for patterned/alternating color. S-CIELAB and
  Yule-Nielsen/Neugebauer work support treating apparent mixed color as a
  spatial/optical question, not a plain swatch arithmetic question.

Sources:

- [Sharma, Wu and Dalal: CIEDE2000 implementation notes and test data](https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/)
- [Celebi: Improving the Performance of K-Means for Color Quantization](https://arxiv.org/abs/1101.0395)
- [Zhang, Silverstein, Farrell and Wandell: S-CIELAB and halftone texture](https://web.stanford.edu/~jefarrel/Publications/1990s/1997_Zhang_Silverstein_Farrell_Wandell.pdf)

## Decisions Applied In 0.4

| Finding | FullSpectrum response |
| --- | --- |
| Uncalibrated blends can look convincing on screen but fail in print | Every prediction is labelled an estimate; add confidence and experimental optical-screen mode |
| More virtual colors can cost complexity without visible gain | Mixes need a configurable visual gain and identical recipes share one logical slot |
| Painted-project corruption is worse than a mediocre palette | Validate exact decoded paint remap, geometry/UV and resources after reopening output |
| Texture references contain information beyond a sparse slot palette | Let reference colors influence anchor choice modestly and report reference similarity |
| Time/material claims require slicing | Report pre-slice complexity and purge context; do not invent print time or filament consumption |

## Fair Comparison Rule

FullSpectrum can be benchmarked against its own reduced-palette variants on
the same painted project. Comparison against Prusa ColorMix is meaningful only
after using the same physical filament samples, printer assumptions and printed
measurement procedure. Until that exists, documentation describes differences
in scope rather than claiming better printed color.
