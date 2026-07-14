# Security And Privacy

FullSpectrum Studio processes files locally. It does not upload source
projects, references or Bambu inventory.

## Inventory

Inventory mode reads the local Bambu Studio Beta `spools.json` file in
read-only mode. Only display-safe color, material and quantity fields are used
inside the local app. Device bindings, tag IDs, spool IDs, quantities and
local paths are not written to generated shareable text reports.

## File Handling

- Output is written as a new `.3mf`; the source is not modified.
- ZIP members are checked against traversal and symlink attacks.
- Uncompressed archive and embedded-reference size limits are enforced.
- GLB embedded images are extracted only to temporary local storage and removed
  after analysis.
- Packaged macOS executables are stripped of local build-path/debug symbols
  before a release archive is made, then the completed app bundle is ad-hoc
  signed and strictly verified. The community preview is not notarized.
- Experimental OBJ/GLB import embeds only the selected model texture in its local
  output project. Users should confirm that texture artwork is appropriate to
  share before publishing generated files.

## Sharing Results

Generated `.3mf` files and screenshots may contain model artwork or displayed
inventory information. Review anything manually before posting it publicly.
The macOS and Windows Copy Error Report actions exclude local paths, model
names, inventory data and raw engine output. Detailed diagnostics are written
only to a private local log and are not copied into the shareable report.
The repository intentionally does not include user model assets, inventory
exports, generated reports or private UI screenshots.
