# FullSpectrum Studio v0.4.12 macOS H2C Prerelease

This macOS-only prerelease focuses on the H2C workflow: faster Best planner
search, clearer palette controls, and a viewport that uses an H2C-sized plate
reference. It keeps the same honest scope as previous releases:
FullSpectrum reduces and remaps existing Bambu painted `.3mf` states. It does
not repaint, smooth or clean up a badly painted model.

## What changed since v0.4.9

- Best planner now uses an adaptive spectrum search. It probes around quality
  `70/100`, reads the resulting error/waste, then jumps only to quality bands
  that are likely to improve the model. Skipped bands are written into the JSON
  result and validation report.
- Anchor shortlisting now keeps hue and neutral spectrum compartments so reds,
  blues, yellows, darks and warm/cool neutrals have a better chance to survive
  into the final physical-slot search.
- The engine builds a target-aware in-memory mix recipe database for the active
  Bambu candidate pool, so repeated anchor trials reuse reconstructed Bambu mix
  colors instead of recomputing the same pair and triple recipes.
- macOS planning can use render-preview weighting. The optimized viewport mesh
  can guide anchor selection for large visible regions while the final `.3mf`
  export still uses the original decoded Bambu paint states.
- The macOS viewer now shows an H2C-oriented `330 x 320` Textured PEI plate
  reference, including a front marker and model-scale-aware plate sizing.
- The app displays the bundle version badge in the lower-right corner.
- Catalog planning and anchor selection can be filtered by Bambu material
  family, with optional pinned anchors and one-click recommended anchors.
- The estimate text uses option-aware local runtime history and model metrics,
  and active progress reports when a deep search is still working rather than
  silently appearing frozen.

## Seraphin private benchmark

The private Seraphin source model was used locally to validate this build. The
source `.3mf`, reference `.glb` and generated model exports are not included in
the repository or release notes.

| Item | Result |
| --- | --- |
| Mode | `official`, `all-bambu`, automatic physical slots, Best planner |
| Planning sample | Render preview weighting with local reference |
| Smart quality tested | `70`, then `100` |
| Smart quality skipped | `35`, `50`, `85` |
| Local wall time | `123.45s` |
| Selected quality | `100/100` |
| Palette | `5` physical anchors, `21` mixed slots, `26` output slots |
| Estimated mean Delta E | `1.45` |
| Estimated max Delta E | `10.94` |
| Quality score | `96.8` |

Screenshots and the full validation narrative are in
[the macOS H2C adaptive planner report](reports/2026-06-01-macos-h2c-adaptive-planner-report.md).

## Validation

- `python3 -m unittest discover -s tests -v` passed: `45` tests.
- `swift build` passed.
- `./script/build_and_run.sh build` produced `dist/FullSpectrum Studio.app`.
- The Desktop copy reports version `0.4.12`, build `14`.
- `codesign --verify --deep --verbose=2` passed for the Desktop app bundle.

## Known limits

- FullSpectrum still remaps existing paint states only.
- Very complex/noisy painted models can still take minutes in Best mode.
- Bambu catalog colors are local planning entries, not live regional stock
  checks.
- Physical print color depends on filament opacity, layer height, lighting and
  calibration; the app validates against Bambu's reconstructed swatches, not a
  measured print.
