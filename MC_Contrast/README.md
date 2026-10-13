# MC Contrast

**MarkCaptures MC Contrast** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

The **Contrast** group of the MarkCaptures PowerGrade (`can_we_make_this_as_a_dctl_1.1.1.drx`), as one DCTL for DaVinci Resolve Studio. The defaults are the PowerGrade's own values. Every node gets a strength slider, plus a few extras on top.

## Install

The package is two items. Drag both into Resolve's LUT folder, side by side and as they are, then *Reload DCTL / LUT list*:

```
LUT/
├── MC_Contrast-v1.1.dctl
└── MarkCaptures/
    └── source/
        ├── MC_Contrast_Density.cube    Density node
        ├── MC_Contrast_Hue.cube        Hue Adjustments node
        ├── MC_Contrast_Contrast.cube   Contrast node
        ├── MC_Contrast_Shadows.cube    Shadows node
        └── MC_Contrast_SatFix.cube     Sat. Fix node
```

The DCTL reads the cubes from `MarkCaptures/source/`, relative to its own location. Keep that folder next to the DCTL (the DCTL may also sit in a subfolder, as long as `MarkCaptures` sits beside it). If a cube is missing, Resolve won't compile the DCTL. The cubes also show up in Resolve's LUT browser under *MarkCaptures › source*. They're inputs for the DCTL, so don't apply them on their own.

The LUT folder is *Project Settings › Color Management › Open LUT Folder*. Typical locations: macOS `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/`, Windows `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\`.

## Node tree

```
[camera log] -> [CST to DWG / DaVinci Intermediate] -> [corrections]
   -> [MC Contrast   Colour Space: DaVinci Wide Gamut Intermediate]
   -> [CST DWG / DaVinci Intermediate -> Rec.709]
```

There's no need for the DWG → ACES and ACES → DWG CSTs around it: the DCTL converts to ACEScct (AP1) and back internally. In an ACEScct timeline, set **Colour Space** to ACEScct.

## What's inside

The nodes run in the PowerGrade's order (read from the node links in the .drx), all in ACEScct:

| # | Node | How it is rebuilt |
|---|---|---|
| 1 | Diffusion | Its curve measured from Resolve's export of the node. It's a pure per-channel curve (checked on colours, error < 0.001), so it is a small table in the DCTL. Middle grey −0.03, white −0.09 (ACEScct). |
| 2 | Density | Resolve's 65-point LUT of the node. |
| 3 | Compensation | HDR Global exposure −0.30 stop. Exact match to the exported LUT. |
| 4 | Hue Adjustments | Resolve's LUT of the node. |
| 5 | Midtones | Rebuilt from its settings: contrast 1.1 @ 0.435 and HDR saturation 0.9, inside the luminance qualifier (low 58.3 %, high 61.4 %, soft 3.4 / 1.4 %). |
| 6 | Contrast | Resolve's LUT of the node. It isn't quite a per-channel curve, so it stays a LUT. |
| 7 | Shadows | Resolve's LUT of the node, its luminance key included. |
| 8 | Sat. Fix | Resolve's LUT of the node. |

Between the LUT nodes the image stays in DWG/DI, the space the LUTs were exported in.

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

- **Midtones key.** In the PowerGrade the key is cleaned up spatially (Denoise 100), which a per-pixel DCTL can't do. With the key's own very narrow soft edges, contrast 1.1 would make the tone curve run backwards at the top of the key. So the soft edges are widened just enough to keep the curve rising (to about 0.037 low and 0.057 high at 100 %). That's also why its LUT export showed almost nothing: a LUT can't hold the spatial key. Midtones is the one node that isn't measured.
- **Shadows key.** Its Denoise 80 is spatial too. The LUT has the key per pixel, as the DCTL does.
- **LUT interpolation.** The Density LUT gives exact greys a sharp lift (+0.04 at about 60 %) that near-greys don't get. Trilinear interpolation smears that spike and bends the grey ramp backwards. So the DCTL reads every LUT at its lattice points and interpolates tetrahedrally itself: greys stay on the LUT's own grey axis, whatever the project's LUT interpolation is set to.
- **Clipped LUT exports.** Resolve clips every LUT it exports to 0–1, but the real nodes push some very dark saturated colours (and some bright ones) past that. Later nodes, like a print emulation or a black lift, bring that range back into view, so a clipped LUT shows as a flat floor in the blacks. `tools/make_luts.py` rebuilds the clipped entries from Resolve's exports in `data/resolve/` as the smoothest continuation of the rest of the LUT (a minimum-curvature fill, limited to −0.25 … 1.25 DI). Every entry Resolve exported unclipped stays exactly as it was.
- **v1.0 → v1.1.** v1.0 rebuilt Diffusion, Hue Adjustments, Contrast and Shadows from the curve points stored in the .drx. Resolve's exports showed that its curves don't pass through those points (they behave more like a Bézier over them). That crushed the shadows: ACEScct 0.10 came out at 0.067 instead of 0.107. v1.1 uses the measured nodes, and matches the chain of exported LUTs to 0.0003 on average.

## Build and test

```
python3 tools/make_luts.py                # rebuild MarkCaptures/source/*.cube from data/resolve/ (a few minutes)
python3 tools/build_dctl.py               # regenerate the DCTL from src/ and tools/mc_contrast.py
python3 tests/test_contrast.py       # compiles the DCTL on the host (C++11 and C99, -Werror) and checks it
```

`tools/mc_contrast.py` is the reference model and holds all the node data. The tests run the generated DCTL on the CPU (with `tests/mca_shim.h`) against it. They check that it matches the model at the defaults and at random settings, returns the exported LUTs on their lattice, follows the measured Diffusion curve, gives an exact Compensation, keeps every grey ramp rising, and follows the DCTL style rules.
