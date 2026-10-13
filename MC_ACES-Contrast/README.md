# MC ACES Contrast

**MarkCaptures MC ACES Contrast** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

The **Contrast** group of the MarkCaptures PowerGrade (`can_we_make_this_as_a_dctl_1.1.1.drx`), as one DCTL for DaVinci Resolve Studio. The defaults are the PowerGrade's own values. Every node gets a strength slider, plus a few extras on top.

## Install

Copy these three files **into the same folder** in Resolve's LUT folder (for example `.../LUT/MarkCaptures/`), then *Reload DCTL / LUT list*:

| File | |
|---|---|
| `MC_ACES-Contrast-v1.0.dctl` | the DCTL |
| `MC_ACES_Contrast_Density.cube` | the Density node (Color Warper + HSV curves) |
| `MC_ACES_Contrast_SatFix.cube` | the Sat. Fix node (Hue vs Sat warper + Chroma-Luma grid) |

The DCTL loads the two cubes from its own folder. If they are missing, Resolve won't compile it.

## Node tree

```
[camera log] -> [CST to DWG / DaVinci Intermediate] -> [corrections]
   -> [MC ACES Contrast   Colour Space: DaVinci Wide Gamut Intermediate]
   -> [CST DWG / DaVinci Intermediate -> Rec.709]
```

There's no need for the DWG → ACES and ACES → DWG CSTs around it: the DCTL converts to ACEScct (AP1) and back internally. In an ACEScct timeline, set **Colour Space** to ACEScct.

## What's inside

The nodes run in the PowerGrade's order (read from the node links in the .drx), all in ACEScct:

| # | Node | How it is rebuilt |
|---|---|---|
| 1 | Diffusion | Its custom curve (Y = R = G = B), from the .drx control points. Rolls off the highlights; white comes down to 0.904. |
| 2 | Density | Resolve's own 65-point LUT of the node (Color Warper Chroma-Luma, HSV-mode curves and its key). |
| 3 | Compensation | HDR Global exposure −0.30 stop. Checked against the exported LUT, which it matches exactly. |
| 4 | Hue Adjustments | Hue vs Hue and Hue vs Sat curves (periodic Bézier, from the .drx). Pulls cyan-blue and blue together by up to 7.5° and takes about 12 % saturation out of blue. |
| 5 | Midtones | Contrast 1.1 @ 0.435 and HDR saturation 0.9, inside the luminance qualifier (low 58.3 %, high 61.4 %, soft 3.4 / 1.4 %). |
| 6 | Contrast | Its custom curve (Y = R = G = B). |
| 7 | Shadows | Its blue curve, inside the inverted luminance qualifier (55.7–99.0 %, low soft 4.8 %, key gain 0.8): a blue lift in the shadows. |
| 8 | Sat. Fix | Resolve's own 65-point LUT of the node. |

## Controls

| Control | Default | |
|---|---|---|
| Blend | 100 | Strength of the whole node. |
| 1 Diffusion … 8 Sat Fix | 100 | Strength of each node in %: 0 = off, 100 = the PowerGrade, up to 200 to push it further. |
| 3 Compensation | −0.30 | Exposure after Density, in stops. |
| Contrast / Pivot | 1 / 0.4135 | Extra contrast after the eight nodes, on ACEScct (0.4135 = 18 % grey). |
| Saturation | 1 | Extra saturation, in linear ACES with the brightness kept. |
| Exposure | 0 | Extra exposure, in stops. |
| Bypass | off | |
| Colour Space | DaVinci Wide Gamut Intermediate | Or ACEScct. |

## Notes and differences from the PowerGrade

- **Midtones key.** In the PowerGrade the key is cleaned up spatially (Denoise 100), which a per-pixel DCTL can't do. With the key's own very narrow soft edges, contrast 1.1 would make the tone curve run backwards at the top of the key. So the soft edges are widened just enough to keep the curve rising (to about 0.037 low and 0.057 high at 100 %). That's also why the Midtones LUT export showed almost nothing: the LUT can't hold the spatial key.
- **LUT interpolation.** The Density LUT gives exact greys a sharp lift (+0.04 at about 60 %) that near-greys don't get. Trilinear interpolation smears that spike and bends the grey ramp backwards. So the DCTL reads the two LUTs at their lattice points and interpolates them tetrahedrally itself: greys stay on the LUT's own grey axis, whatever the project's LUT interpolation is set to.
- **Interpretations still to confirm against Resolve LUT exports.** Resolve's file format isn't documented, so these come from reading the .drx:
  - linked Y/R/G/B curves act once per channel;
  - curves are monotone cubics through their points;
  - the Hue curve x axis starts at red, Hue vs Hue moves hue by (y − 0.5) of a turn and Hue vs Sat scales chroma by 2y;
  - the Shadows key is inverted, and its 0.8 is the key output gain.

## Build and test

```
python3 tools/build_dctl.py               # regenerate the DCTL from src/ and tools/mc_aces_contrast.py
python3 tests/test_aces_contrast.py       # compiles the DCTL on the host (C++11 and C99, -Werror) and checks it
```

`tools/mc_aces_contrast.py` is the reference model and holds all the node data. The tests run the generated DCTL on the CPU (with `tests/mca_shim.h`) against it. They check that it matches the model at the defaults and at random settings, returns the exported LUTs on their lattice, gives an exact Compensation, keeps every grey ramp rising, and follows the DCTL style rules.
