# Validation And Testing

## Automatic Checks

- Known Bambu paint state decoding and embedded slot remapping.
- No missing paint slot references after writing.
- Physical/mixed slot ordering, component validity, ratios and non-recursion.
- Aligned filament arrays and correctly resized square purge matrices.
- No zero off-diagonal purge transition in an output purge matrix.
- Reopen-and-validate of the written `.3mf`.
- SHA-256 preservation of texture/resources and normalized model data, allowing
  only `paint_color` changes in object models.
- Safe ZIP extraction rejection for traversal/symlink/oversize input.

## Running Tests

```bash
python3 -m unittest discover -s tests -v
swift build -c debug
./script/build_and_run.sh build
```

## Regression Samples

Keep sample model files local, because real `.3mf` projects can contain private
names, preview imagery or inventory details. Useful local cases are:

- A minimal one-object project with two painted colors.
- A complex painted model with serialized extended paint codes.
- Projects with complete purge matrices and several filament-array widths.
- A GLB with embedded texture plus the corresponding painted `.3mf`.
- Malformed and traversal ZIP fixtures generated in tests.

## Benchmark Plan

Measure conversion time and peak memory for small, medium and large painted
objects, including a several-hundred-megabyte model. Record paint code count,
physical/mixed slot count, quality score and validation outcome. Large local
assets are deliberately excluded from the public repository.
