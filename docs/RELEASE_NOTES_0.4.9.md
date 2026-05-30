# FullSpectrum Studio v0.4.9 Official Release

This release is the first official package after the v0.4.8 community
reliability preview. It keeps the same honest scope: FullSpectrum reduces and
remaps existing Bambu painted `.3mf` states. It does not repaint, smooth or
clean up a badly painted model.

## What changed

- Smart quality is now the recommended default. It tests practical, balanced,
  detail and high-detail plans, scores the final validated palette, and keeps
  the best tradeoff for the painted usage in that model.
- Physical anchor selection now favors filament choices that produce better
  final Bambu-reconstructed mixed swatches, not just closer direct colors.
- macOS and Windows both expose a catalog-region selector for Bambu planning
  colors. The chosen region is written into warnings, JSON output and the
  shareable report.
- Catalog regions are planning metadata only. FullSpectrum does not query live
  Bambu store stock, so check availability before buying filament.
- The v0.4.8 fixes remain in place: real error reports, local debug logs,
  cancellable conversion, progress heartbeat text, readable dark-mode controls
  and safer large-model preview handling.

## Compatibility

- Primary input remains a painted Bambu `.3mf`.
- Textured OBJ/GLB import remains experimental and size/format constrained.
- Very complex or noisy painted files can still be slow or visually imperfect,
  because the output can only be as clean as the original paint-state data.
- Every generated `.3mf` is reopened and validated before the app offers it to
  Bambu Studio or OrcaSlicer.

## Validation used for this release

- `python3 -m unittest discover -s tests -v`
- `swift build`
- `./script/build_and_run.sh build`
- Local conversion checks for catalog-region output, smart Bambu Core planning
  and CMYKW quality-100 planning on the public bald-eagle test model used
  during the v0.4.8 reliability pass.
