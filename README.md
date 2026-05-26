# FullSpectrum Studio

FullSpectrum Studio is a local desktop workflow for reducing the physical
filament count of painted Bambu Studio `.3mf` projects while trying to preserve
their original painted appearance.

It creates a separate converted `.3mf`, a recipe CSV and a validation report.
The source project is never modified.

This is an independent community preview built around the H2C public-beta
workflow and is not affiliated with Bambu Lab.

## What It Does

- Reads Bambu `paint_color` information directly from the project instead of
  assuming paint order equals filament order.
- Chooses `2–6` physical filament anchors automatically or manually and places
  generated mixed recipes after the physical slots.
- Supports local Bambu Studio Beta inventory in read-only mode, supported
  Bambu PLA planning palettes, CMYKW workflows and custom local filament
  libraries.
- Accepts an optional `.obj`, `.glb` or texture image as a visual reference and
  reports an estimated similarity score.
- Provides preview, progress feedback, recipe display, quality estimates and
  optional opening of the validated result.

---

## Validation

Outputs are validated before export.

The engine rejects outputs if:

- A `paint_color` references a slot that does not exist.
- A mixed slot references itself, another mixed slot, duplicate components or
  components outside the selected physical slots.
- Slot arrays or purge matrices become invalid.
- Geometry, UV data or source textures are unintentionally modified.

Archive extraction is handled defensively and unsafe archive paths or abnormal
archive sizes are rejected.

---

## Filament Choices

### My Inventory

Recommended for practical printing.

Uses only active PLA spools detected in the local Bambu Studio Beta inventory
and estimates available mixing capacity from remaining material.

### Bambu Core

Uses supported:

- PLA Basic
- PLA Matte
- PLA Silk+

### All Bambu

Allows additional Bambu PLA families discovered locally.

Catalog colors are suggestions only — confirm regional availability before
buying.

### Exact CMYKW

Assigns literal CMYKW roles.

### CMYKW + Inventory

Maps those roles to owned colors and warns when similarity becomes poor.

Mixed-color preview and quality estimates are visual approximations and not a
replacement for printer calibration.

### Custom Brands

Accepts a JSON file using:

`examples/custom-palette.example.json`

---

## Reference Mode

Reference mode samples texture information from:

- `.glb`
- `.obj` material textures
- image files

It compares dominant colors against the predicted reduced palette.

Reference mode acts as an optimization target and before/after aid.

It does not convert raw OBJ/GLB geometry into printable Bambu projects.

Conversion still requires a painted `.3mf` as the source and output structure.

---

## macOS App

Requirements:

- macOS 14+
- Swift 5.9
- Xcode Command Line Tools
- Python included with macOS

Build:

```bash
./script/build_and_run.sh build
./script/build_and_run.sh run
