# Validation Benchmark

## Method

These are local single-run engineering checks performed on 2026-05-27 on the
development Mac. Private source models and inventory data are not distributed.
Times and memory are useful for regression detection, not hardware-independent
performance claims. Quality values are planning estimates, not printed color
measurements.

Every successful conversion below reopened the written `.3mf` and validated:

- filament-array and purge-matrix alignment;
- physical/mixed component rules;
- output paint-state references and exact decoded remap equivalence;
- preservation of existing geometry, UV-bearing model content and resources.

## Workloads

| Workload | Purpose | Result | Wall time | Peak resident memory | Output |
| --- | --- | ---: | ---: | ---: | ---: |
| Small synthetic painted `.3mf` | Fast schema/regression path | Validated, `2` physical + `2` mixed | `0.09 s` | `25.6 MB` | `903 B` |
| Medium textured OBJ, 305,283 triangles, 4096 px texture | Experimental import and Bambu color compression | Validated, `4` physical + `11` mixed | `67.01 s` | `309.2 MB` | `43.8 MB` |
| Large painted `.3mf` with texture reference and two analysis overlays | Primary workflow plus viewer artifacts | Validated, `3` physical + `6` mixed | `62.64 s` | `91.7 MB` | `85.5 MB` |
| Extreme raw GLB above two-million-face import limit | Failure/safety path | Rejected before geometry buffer decode | `0.05 s` | `25.5 MB` | No output |

## Quality Tradeoff Check

One private large painted project was planned with the same catalog and visual
reference at three quality-versus-waste settings:

| Setting | Physical | Mixed | Painted mixed share | Estimated quality | Mean Delta E | Contrast retention | Complexity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Practical (`20`) | 3 | 6 | 31.4% | 85.5 | 6.57 | 60.2% | Medium |
| Balanced (`60`) | 3 | 6 | 31.4% | 85.5 | 6.57 | 60.2% | Medium |
| Detail (`90`) | 5 | 11 | 55.5% | 88.9 | 5.02 | 81.9% | High |

On this sample, Balanced correctly avoids extra mixed slots unless the user
explicitly moves toward Detail. Detail estimates a better match, at the cost
of two more physical colors, five more mixed colors and higher printability
complexity.

## Stabilization Measurements

Two v0.4 stabilization changes were measured on the real workloads:

| Change | Before | After | Outcome |
| --- | ---: | ---: | --- |
| Compact texture sampling and streamed OBJ model XML, preview workload | `590.2 MB` peak | `309.1 MB` peak | `47.6%` lower peak resident memory |
| Reuse geometry for heatmap and anchor-influence overlays, large conversion | `96.82 s`, `106.6 MB` | `62.64 s`, `91.7 MB` | `35.3%` less wall time and lower peak memory |

### v0.4.1 Open-Path Guard

A local painted `.3mf` containing `5,417,070` triangles exposed that optional
viewer generation must not be part of opening a project. With v0.4.1:

| Action | Outcome | Time | Peak resident memory |
| --- | --- | ---: | ---: |
| Fast metadata/palette open | Opens without constructing a 3D mesh | `0.06 s` | `25.9 MB` |
| Bounded interactive-preview request | Reports that the optional mesh is omitted and preserves plate preview | `3.96 s` | `25.9 MB` |

The same budget is applied to optional heatmap/anchor-influence mesh creation;
conversion and `.3mf` validation still run when overlays are omitted.

## Viewer Notes

The native viewer exposes `Fast`, `Balanced`, `High` and `Maximum` rendering
presets with frame-rate targets of `24`, `30`, `45` and `60` FPS. Actual
delivered FPS depends on model complexity and hardware and is not claimed by
this benchmark.

## Reproducing Quality Variants

```bash
python3 tools/benchmark_quality.py --palette-source catalog \
  --reference source.glb painted-project.3mf
```

Run real print-time, purge and gram comparisons only after slicing the
validated output in the target slicer and printer configuration.
