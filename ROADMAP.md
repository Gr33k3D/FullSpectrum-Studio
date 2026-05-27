# Roadmap

## Current: 0.4 Community Preview

Shipping now:

- Validated painted `.3mf` conversion with decoded Bambu paint remapping.
- Inventory, Bambu planning, exact CMYKW and custom filament sources.
- CIEDE2000 scoring, adaptive physical anchors and gain-limited mixed recipes.
- Confidence, contrast and printability complexity reporting.
- Original, reduced/predicted, heatmap, anchor-influence and wireframe native views.
- Experimental constrained textured OBJ/GLB to validated `.3mf` conversion.
- macOS application and Windows portable/installer packaging.

## Next: Measurement And Recommendations

- Local calibration-card workflow for owned colors and mixed ratios.
- Recommend the single best additional owned/purchasable anchor, with
  availability clearly separated from color prediction.
- Import sliced statistics for real print time, purge and filament usage.
- Benchmark reports based on measured prints rather than preview-only values.

## Later: Source Import Coverage

- Broader GLB material, texture and compression support after additional
  transform/primitive/UV regression fixtures.
- Spatial texture-loss map with efficient level-of-detail sampling.
- Side-by-side and overlay synchronization in the native viewer.

## Non-Goals

- Replacing Bambu Studio as a slicer.
- Publishing printer-agnostic claims of exact optical mixed color.
- Using private inventory data anywhere outside the local device.
