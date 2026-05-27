# Validation And Testing

## Automatic Checks

- Known Bambu paint state decoding and embedded slot remapping.
- Exact comparison of written paint-state counts against decoded expected
  remapping, rather than merely checking that slots exist.
- No missing paint slot references after writing.
- Physical/mixed slot ordering, component validity, ratios and non-recursion.
- Synchronization of `filament_colour` and `filament_multi_colour`, with each
  mixed swatch reconstructed using Bambu Studio component/ratio behavior.
- Aligned filament arrays and correctly resized square purge matrices.
- No zero off-diagonal purge transition in an output purge matrix.
- Reopen-and-validate of the written `.3mf`.
- SHA-256 preservation of texture/resources and normalized model data, allowing
  only `paint_color` changes in object models.
- Safe ZIP extraction rejection for traversal/symlink/oversize input.
- CIEDE2000 published reference-pair calculation.
- Bambu mixer regressions for purple, green, orange, neutral and dark mixes,
  and loaded-color swatches observed in the real angel benchmark.
- Rejection of a misleading black/pink purple recipe when the reconstructed
  output cannot meet the Delta E reliability limit.
- Gain-limited mix reuse, quality-bias behavior, analysis meshes and constrained
  textured OBJ/GLB import/rejection cases.

## Running Tests

```bash
python3 -m unittest discover -s tests -v
swift build -c debug
./script/build_and_run.sh build
```

The suite currently includes `28` synthetic/regression and security tests,
including rejection of over-limit GLB import before geometry decoding and a
shareable-report reference-filename privacy check. It also tests lightweight
metadata opening and grid-reduced optimized preview/analysis fallbacks for
oversized models.

## Regression Samples

Keep sample model files local, because real `.3mf` projects can contain private
names, preview imagery or inventory details. Useful local cases are:

- A minimal one-object project with two painted colors.
- A complex painted model with serialized extended paint codes.
- Projects with complete purge matrices and several filament-array widths.
- A GLB with embedded texture plus the corresponding painted `.3mf`.
- A textured OBJ with complete UVs and PNG/JPEG texture, and a constrained GLB
  with embedded texture, for experimental import; reject unsupported or
  image-only conversion.
- Malformed and traversal ZIP fixtures generated in tests.

## Benchmark Plan

Use `python3 tools/benchmark_quality.py project.3mf --reference source.glb`
to compare Practical, Balanced and Detail settings locally. Record paint code
count, physical/mixed slot count, quality, confidence, contrast and validation
outcome. Conversion time and peak memory should also be recorded for small,
medium and large painted objects. Large local assets are deliberately excluded
from the public repository.
