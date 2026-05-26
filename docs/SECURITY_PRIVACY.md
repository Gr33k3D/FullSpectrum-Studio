# Security And Privacy

FullSpectrum Studio processes files locally. It does not upload source
projects, references or Bambu inventory.

## Inventory

Inventory mode reads the local Bambu Studio Beta `spools.json` file in
read-only mode. Only display-safe color, material and quantity fields are used
inside the app. Device bindings, tag IDs, spool IDs and local paths are not
written to recipe or validation reports.

## File Handling

- Output is written as a new `.3mf`; the source is not modified.
- ZIP members are checked against traversal and symlink attacks.
- Uncompressed archive and embedded-reference size limits are enforced.
- GLB embedded images are extracted only to temporary local storage and removed
  after analysis.

## Sharing Results

Generated `.3mf` files and screenshots may contain model artwork or displayed
inventory information. Review anything manually before posting it publicly.
The repository intentionally does not include user model assets, inventory
exports, generated reports or private UI screenshots.
