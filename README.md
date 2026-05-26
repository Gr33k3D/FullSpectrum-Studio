# FullSpectrum Studio

FullSpectrum Studio is a local desktop workflow for reducing the physical
filament count of painted Bambu Studio `.3mf` projects while preserving the
project's painted-facet meaning. It creates a separate converted `.3mf`, a
recipe CSV and a validation report. The source project is never overwritten.

This is an independent community preview for experimentation with the H2C
public-beta workflow. It is not affiliated with Bambu Lab.

## What It Does

- Decodes Bambu's serialized `paint_color` states from the model itself; it
  does not assume that code order equals filament order.
- Chooses `2-6` physical filament anchors, automatically or explicitly, then
  places generated mixed recipes after the physical slots.
- Uses local Bambu Studio Beta inventory in read-only mode, a supported Bambu
  PLA planning palette, exact CMYKW roles, or a custom local filament library.
- Accepts an optional `.obj`, `.glb` or texture image as a visual reference and
  reports an estimated similarity score.
- Provides a movable painted preview on macOS, progress, recipe display,
  quality estimates and optional opening of the validated result.

## Validation Guarantees

Every output is reopened before it is accepted. The engine rejects an output if:

- A `paint_color` state refers to a slot that does not exist.
- A mixed slot references itself, another mixed slot, a duplicate component or
  a component outside the selected physical slots.
- Slot arrays or purge matrices are misaligned, or an output purge matrix
  contains a zero off-diagonal transition.
- Any object geometry or UV-bearing model data changed beyond `paint_color`, or
  any source texture/resource changed byte-for-byte.

The converter reads ZIP contents defensively and rejects unsafe archive paths
and excessive uncompressed archive sizes.

## Filament Choices

`My Inventory` is the safest practical option: it selects only active PLA
spools visible in the local Bambu Studio Beta inventory and estimates mix
capacity from remaining material.

`Bambu Core` plans with supported PLA Basic, PLA Matte and PLA Silk+ colors.
`All Bambu` additionally permits other active Bambu PLA families discovered in
your local inventory. Catalog colors are planning suggestions; confirm
regional availability before buying.

`Exact CMYKW` assigns literal CMYKW roles. `CMYKW` with inventory maps those
roles to owned colors and shows a warning when the match is poor. Mixed-color
preview and quality scores are perceptual estimates, not printer calibration.

`Custom Brands` accepts a JSON file in the format shown at
[examples/custom-palette.example.json](examples/custom-palette.example.json).

## Reference Mode

Reference mode samples the texture from a `.glb`, an OBJ material texture, or
an image and compares dominant colors with the predicted reduced palette. It is
an optimization target and before/after aid; it does not turn raw OBJ/GLB
geometry into a printable Bambu project. Conversion still requires a painted
`.3mf` as the output structure and paint source.

## macOS App

Requirements: macOS 14 or newer, Swift 5.9 / Xcode command-line tools, and
Python 3 supplied with macOS.

```bash
./script/build_and_run.sh build
./script/build_and_run.sh run
```

The built application is written to `dist/FullSpectrum Studio.app`.

## Windows App

Windows uses the same Python conversion and validation engine in a compact
desktop shell. Tagged releases build both a portable ZIP and an installer using
the workflow in [.github/workflows/windows-release.yml](.github/workflows/windows-release.yml).
The macOS orbitable SceneKit preview is not present in this initial Windows UI.

## Command Line

```bash
python3 fullspectrum_engine.py --mode official --palette-source inventory \
  --real-slots auto --reference original.glb painted-project.3mf
```

## Privacy And Safety

- Inventory access is local and read-only. No spool identifiers are written to
  output reports or committed assets.
- Generated projects, local inventories and private screenshots are ignored by
  version control.
- Before printing, verify filament assignments, purge values and slicing in
  Bambu Studio; appearance still depends on physical filament and calibration.

Further detail: [Architecture](docs/ARCHITECTURE.md), [Validation and Testing](docs/VALIDATION.md),
[Security and Privacy](docs/SECURITY_PRIVACY.md), and [0.3 Release Notes](docs/RELEASE_NOTES_0.3.md).

## License

Released under the [PolyForm Noncommercial License 1.0.0](LICENSE). It is
shared for non-commercial community use and modification; it is not an
OSI-approved open-source license and does not permit commercial exploitation.
