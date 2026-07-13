# FullSpectrum Studio macOS H2C Adaptive Planner Report

Date: 2026-06-01

Build: `FullSpectrum Studio.app` `0.4.12` (`14`)

Scope: macOS H2C prerelease only. This report does not include a Windows build.

Privacy note: a private `.3mf` and reference `.glb` were used as local test
inputs only. Their names, screenshots, source files and generated model exports
are not included in the current repository tree.

## Baseline

The previous GitHub baseline was `v0.4.9` at commit `9f2f2ad`:
`Prepare v0.4.9 official release`.

That release already contained the v0.4.8 reliability fixes: real Python
stderr/stdout capture, copyable error reports, local debug logs, cancellable
conversion, progress heartbeats, readable dark-mode controls and safer
large-model preview handling.

## What changed since v0.4.9

### Adaptive Planner

- Best mode now starts with a `70/100` quality probe instead of walking every
  quality band.
- The probe result decides the next band. If the palette is too inaccurate, the
  planner jumps up toward `100`; if it is clean but wasteful, it jumps down
  toward `50` or `35`.
- Bands that cannot plausibly improve the result are skipped and written to
  the JSON/report as `skippedQualityCandidates`.
- This directly targets the old behavior where the UI could sit for many
  minutes while testing intermediate bands that were unlikely to matter.

### Spectrum-Compartment Anchor Search

- Anchor shortlisting now groups important targets into hue and neutral
  compartments before global scoring.
- This keeps saturated reds, yellows, blues, darks and warm/cool neutrals from
  being crowded out by one locally good global nearest-color choice.
- The approach is still deterministic and uses real Bambu filament candidates
  from the selected material/source filters.

### Cached Bambu Mix Recipe Matrix

- The engine now builds a target-aware in-memory database of useful two-color
  and three-color Bambu halftone recipes for the active candidate pool.
- Anchor beam trials reuse those reconstructed recipes, rather than repeatedly
  recomputing the same mix colors for each possible anchor set.
- The 32-color Bambu paint-slot limit is not the expensive part; the expensive
  part was scoring physical anchor sets against many possible reconstructed
  mixes.

### H2C macOS Viewer

- The render floor is now an H2C-oriented `330 x 320` Textured PEI reference
  plate.
- The plate has a front marker, grid, center crosshair and scale-aware sizing
  so the loaded model has a useful visual reference.
- The viewer still preserves the existing model orientation handling and
  optimized large-model preview path.

### macOS UI And Workflow Additions

- Version badge overlay remains visible in the lower-right corner.
- Render-preview planning can use the optimized viewport mesh as a visual
  weighting sample before full conversion.
- Material-family filters and anchor pinning are exposed for Bambu catalog
  planning.
- The app can recommend anchors and then let the user lock them before running
  the compose step.
- Active conversion messages explain when the deep planner is still working,
  what quality band is being tested and when a plan is past its estimate.

## Private Benchmark

Command shape:

```bash
python3 fullspectrum_engine.py /private/path/model.3mf \
  --mode official \
  --palette-source all-bambu \
  --real-slots auto \
  --quality-bias auto \
  --planner-mode best \
  --planning-sample preview \
  --reference /private/path/reference.glb \
  --plan-preview \
  --json \
  --no-reveal
```

Observed local result:

| Metric | Value |
| --- | --- |
| Preview sample | `17` visible painted slots |
| Smart search mode | `adaptive-spectrum` |
| Tested quality bands | `70`, `100` |
| Skipped quality bands | `35`, `50`, `85` |
| Wall time | `123.45s` |
| Selected quality | `100/100` |
| Physical anchors | `5` |
| Mixed slots | `21` |
| Output slots | `26` |
| Estimated mean Delta E | `1.45` |
| Estimated max Delta E | `10.94` |
| Quality score | `96.8` |
| Reference similarity | `85.8` |

The test produced a warning that preview-weighted planning was used. That is
expected: the preview mesh is only used to weight planning. The final exported
`.3mf` is still written from the exact original Bambu paint states.

## Validation

- Python engine tests: `python3 -m unittest discover -s tests -v`
  - Result: `45` tests passed.
- Swift package build: `swift build`
  - Result: passed.
- macOS app package: `./script/build_and_run.sh build`
  - Result: `dist/FullSpectrum Studio.app` built successfully.
- Packaged app:
  - Result: `dist/FullSpectrum Studio.app` reports version `0.4.12`, build `14`.
- Code signature:
  - Result: `codesign --verify --deep --verbose=2` passed for the Desktop app.

## Remaining Limits

- FullSpectrum reduces/remaps existing Bambu paint states. It does not repaint,
  smooth or clean up a bad source paint job.
- Very complex/noisy painted files can still take minutes in Best mode. The
  new adaptive planner reduces wasted quality-band work, but high-fidelity
  anchor/mix search is still expensive by design.
- Catalog colors come from installed/local Bambu planning data. The app does
  not query live Bambu store stock.
- Predicted mixed colors match Bambu Studio's reconstructed swatches. Physical
  prints can still drift due to opacity, layer height, temperature, lighting,
  surface finish and calibration.

## Pasteable GitHub/Forum Summary

I pushed a macOS H2C prerelease of FullSpectrum Studio focused on the slow Best
planner cases. The planner now starts with an adaptive `70/100` quality probe,
splits anchor candidates into hue/neutral spectrum groups, reuses a cached
Bambu mix-recipe matrix, and skips quality bands that are unlikely to help.

On a private local test model the plan-preview path tested quality `70`
and `100`, skipped `35/50/85`, and completed locally in about `2m03s` with
`5` physical anchors, `21` mixed slots and `26` output slots. The macOS viewer
now also shows an H2C-style `330 x 320` Textured PEI plate with a front marker
and the version badge remains visible in the corner.

Important limitation: FullSpectrum still remaps existing Bambu paint states.
It does not repaint or smooth the model, so badly painted or very noisy source
files can still produce imperfect results or take longer.
