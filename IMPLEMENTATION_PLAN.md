# Implementation Plan And Status

## Released Implementation Scope

| Area | Status | Verification |
| --- | --- | --- |
| Paint-code decoding and remapping | Implemented | Known Bambu codes and expected-state equivalence tests |
| ZIP/schema/purge/mixed-slot safety | Implemented | Archive, array and purge regression tests |
| CIEDE2000 engine | Implemented | Published reference-pair test |
| Bambu reconstructed mix suppression and recipe reuse | Implemented | Loaded-swatch, reliability-limit, bias monotonicity and duplicate recipe tests |
| Reference-aware quality metrics | Implemented | Reference conversion test and private real-model run |
| Loss/influence viewport assets and large-model fallback | Implemented | Standard and optimized mesh-generation regression tests |
| Textured OBJ import | Experimental | UV/texture validated synthetic fixture |
| Constrained textured GLB import | Experimental | Embedded-texture transformed synthetic fixture |
| Broader GLB material/compression import | Deferred | Reject unsupported primitives explicitly |
| Actual time/material/swap estimate | Deferred | Requires sliced toolpath/statistics input |

## Validation Sequence

1. Reject unsafe or malformed source archives.
2. Decode source paint states and count painted slot usage.
3. Select physical anchors and only logical mixes whose serialized,
   Bambu-reconstructed color is both beneficial and within the reliability
   limit.
4. Remap paint states by decoding and re-encoding their referenced slots.
5. Resize aligned filament arrays and purge matrices.
6. Write a separate output archive.
7. Reopen it, validate every slot/mix/array/purge rule, compare output paint
   state counts to the expected decoded remap and reconstruct every saved mix
   using Bambu's loaded-swatch behavior.
8. Compare geometry, UV-bearing object content and source resources.
9. Only then return reports and allow opening in Bambu Studio.

## Benchmark Procedure

`tools/benchmark_quality.py` runs the Practical, Balanced and Detail planning
settings against a local painted project and optional reference. It reports
quality, confidence, contrast, mixed-slot count and pre-slice complexity.

It deliberately does not claim a printed comparison to Prusa or Orca. A fair
cross-workflow benchmark would require equivalent physical filament samples,
printed specimens and measured or controlled photographic evaluation.
