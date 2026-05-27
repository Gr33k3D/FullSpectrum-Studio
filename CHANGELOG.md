# Changelog

## 0.4.0 Community Preview - 2026-05-27

### Changed

- Uses CIEDE2000 for palette scoring and reports estimated confidence,
  brightness preservation and contrast retention.
- Adds quality-versus-waste planning, visual-gain gating for mixed slots and
  reuse of identical mixed recipes.
- Validates the exact decoded paint-state remap after reopening every written
  `.3mf`.
- Adds reduced/predicted, heatmap, anchor-influence and wireframe views in the
  macOS application, with model/load statistics and render presets.
- Adds experimental constrained textured OBJ and embedded-texture GLB import,
  routed through the same validator as painted `.3mf` conversion.
- Makes Windows controls and output reporting follow the shared v0.4 engine.

### Stabilized

- Streams imported OBJ model XML and stores sampled image pixels compactly to
  reduce peak memory for large textured inputs.
- Rejects GLB sources declaring more than two million faces before loading
  their binary geometry payload.
- Generates analysis overlays from one reduced viewport geometry pass.
- Makes cancellation, session replacement and Finder/Explorer output reveal
  predictable.
- Removes local reference filenames and inventory paths from generated
  shareable reports.

### Compatibility

- Existing painted `.3mf` input remains the supported primary workflow.
- Textured OBJ/GLB source import is experimental and rejects unsupported
  texture, primitive, UV or size cases explicitly.
- Outputs remain separate files; source projects are not overwritten.

## 0.3.0 Community Preview - 2026-05-26

- First public preview with decoded Bambu paint remapping, physical/mixed slot
  validation, local reference scoring, macOS viewer and Windows packaging.
