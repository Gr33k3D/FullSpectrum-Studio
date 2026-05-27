# Product Ideas

These ideas are filtered through FullSpectrum Studio's identity: protecting
painted project meaning while producing a practical, validated output.

## Implemented In 0.4

- CIEDE2000 palette scoring with a standard-reference unit test.
- Texture/reference-aware anchor scoring without letting the reference replace
  paint usage.
- Quality-versus-waste control that suppresses weak mixed colors.
- Reuse of identical mixed recipes to avoid duplicate logical slots.
- Bambu-compatible loaded-swatch prediction shared by planning, export
  validation and preview; the earlier optical-screen experiment was removed.
- Confidence, brightness-error, contrast-retention and pre-slice printability
  indicators.
- Color-loss and anchor-influence analysis meshes for the native viewer.
- Experimental textured OBJ/GLB import with UV/texture embedding, deterministic
  color clustering and compression warnings at the Bambu paint-color limit.
- Exact expected-versus-written paint-state validation after archive reopen.
- Reliable-match gating that refuses mixed targets outside Delta E `8`.
- Sampled optimized large-model preview and analysis overlays.

## Valuable Next Experiments

| Idea | Why it fits | Gate before shipping |
| --- | --- | --- |
| User-printable calibration card and measured filament profiles | Converts uncertainty into data for owned filament | Repeatable capture/lighting protocol and local-only storage |
| Spatial heatmap based on UV texture pixels rather than paint slots | Locates lost detail instead of averaging it | Efficient texture-to-surface sampling for large models |
| Inventory recommendation path | Shows which one added physical color removes the most high-error mixes | Availability must remain user-confirmed |
| Sliced-result import for actual toolchanges/purge/time | Makes printability estimates honest and actionable | Support Bambu exported sliced statistics without editing G-code |
| Broader GLB material/compression coverage | Supports more source exports without weakening validation | Accessor/material/transform/UV regression corpus |

## Ideas Rejected Or Deferred

- Do not copy Prusa ColorMix calibration values: they are not measurements of
  the user's Bambu or custom filaments.
- Do not generate unsupported time or filament estimates from unsliced facets.
- Do not imply that PNG/JPG alone is printable geometry.
- Do not create more than Bambu-compatible paint slots simply because internal
  analysis can represent them; compress with a warning before export.
- Do not turn the application into a slicer fork or toolpath generator.
