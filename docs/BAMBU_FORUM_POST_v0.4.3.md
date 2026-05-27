# Bambu Forum Update Draft - v0.4.3

Hi everyone, I wanted to share a proper update to **FullSpectrum Studio**.

I started this because I had painted multicolor models that looked great, but
were not very practical to print with a smaller physical filament setup. I am
not a developer by background, so this has been a lot of testing, learning and
checking real files. I am sharing it as a community preview because I wanted
to give something useful back.

**What it does**

FullSpectrum Studio takes an already painted Bambu `.3mf`, chooses a reduced
set of real filaments, creates useful mixed filament recipes where they
actually help, writes a new `.3mf`, and validates it before opening it in
Bambu Studio. The original file is left untouched.

**The important v0.4.3 fix**

I found a trust-breaking problem: the app could show a nice mixed color, but
Bambu Studio could load a different visible color from the exported recipe.
The new version now reconstructs mixed swatches the same way Bambu loads them,
uses that one result for the viewer and export, and reopens the finished file
to check it.

There was also a confusing purple example in my angel model. The original
painted project really contains purple target colors. Previously the recipe
display made it too easy to read a target color as the produced result. The
app now shows **target -> Bambu reconstructed output** separately, and it will
not create a mixed recipe if the result is still a poor color match. It warns
that a closer real filament is needed instead.

**Other changes**

- The 3D viewer is now the main workspace and supports fullscreen, predicted,
  validation, heatmap, anchor-influence and wireframe views.
- Very large models use an optimized movable display mesh instead of showing a
  blank viewer or trying to render millions of triangles directly.
- My Inventory mode reads the local Bambu Studio Beta inventory read-only and
  now shows installed Bambu filament names when the local catalog provides
  them.
- Bambu Core, All Bambu, exact CMYKW and custom local palette modes are also
  available, so inventory mode is optional.
- Output validation covers paint mapping, geometry/UV/resources, filament
  arrays, mixed-slot rules, purge matrices and loaded mixed-color
  reconstruction.

**Screenshots**

Predicted result and validation:

![FullSpectrum Studio predicted preview](https://github.com/Gr33k3D/FullSpectrum-Studio/blob/main/teasers/v0.4.3-predicted.png?raw=true)

Color-loss heatmap:

![FullSpectrum Studio heatmap](https://github.com/Gr33k3D/FullSpectrum-Studio/blob/main/teasers/v0.4.3-heatmap.png?raw=true)

Anchor-influence view:

![FullSpectrum Studio anchor view](https://github.com/Gr33k3D/FullSpectrum-Studio/blob/main/teasers/v0.4.3-anchor.png?raw=true)

**Relation to Prusa ColorMix**

I followed the recent ColorMix news with interest, but this is a different
workflow. FullSpectrum starts from an already painted Bambu project and focuses
on reducing its physical palette, planning recipes and producing a validated
Bambu `.3mf`. It is not a slicer and does not copy Prusa's calibration model.

**Limits**

This is still a community preview. Matching the color Bambu displays is not
the same as guaranteeing the physical print color; filament, layer behavior,
lighting and calibration still matter. I strongly recommend a small test print
before a long color-sensitive model. OBJ and GLB source import remain marked
experimental.

GitHub and downloads:
[FullSpectrum Studio](https://github.com/Gr33k3D/FullSpectrum-Studio)

License: PolyForm Noncommercial 1.0.0. I am sharing it for non-commercial
community use, not for others to sell.

Thank you to anyone who tries it and reports what works or fails. Honest
feedback is the best way for me to make this more useful.
