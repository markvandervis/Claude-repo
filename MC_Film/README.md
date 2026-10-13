# MC Film

**MarkCaptures MC Film** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

MC Film is a film emulation suite for DaVinci Resolve Studio. It starts as DCTLs and becomes an OFX plugin later. The colour maths is written once, so each DCTL is a straight port target for the plugin.

Stock data: derived from **spektrafilm by Andrea Volpato** (https://github.com/andreavolpato/spektrafilm), licensed **CC BY-SA 4.0**. See `LICENSE.txt` and `data/CHANGELOG.txt`. The film engine itself is an independent implementation; no spektrafilm code is used.

---

## MC Film Core v0.5: negative + print engine

`MC_Film-Core-v0.5.dctl`

A physically based simulation: the scene is exposed onto a colour negative, developed, printed with printer lights onto a print stock, then projected and viewed.

1. **Exposure onto the negative.** The Mallett & Yuksel 2019 spectral basis, lit by the stock's reference light (daylight or tungsten), against the stock's measured layer sensitivities.
2. **Development.** Each layer's measured characteristic curve, with Exposure, Push/Pull and Negative Contrast.
3. **Printing.** A 41-band spectral calculation: printer lamp × the negative's measured dyes and orange mask × the print stock's layer sensitivities. Printer lights are in Kodak printer points (1 point = 0.025 log E).
4. **Print development.** The print stock's measured curves, with Print Contrast.
5. **Projection.** The print dyes under the stock's viewing light (a xenon projector for 2383/2393, D50 for papers), CIE 1931 observer, adapted to D65, then the display encoding.

Each negative and print pair is timed so that a scene 18% grey prints as a neutral grey at the laboratory aim density (1.0).

**Stocks**
- Negatives: Kodak Vision3 50D / 250D / 200T / 500T, Portra 160 / 400 / 800, Ektar 100, Gold 200, Ultramax 400, Fujifilm Pro 400H, C200, Xtra 400.
- Prints: Kodak 2383, 2393, Portra Endura, Endura Premier, Supra Endura, Ultra Endura, Ektacolor Edge, Fujifilm Crystal Archive.

**Controls**

| Control | What it does |
|---|---|
| Exposure | Camera exposure onto the negative, in stops |
| Scene Temp / Scene Tint | White balance of the scene *before* the film, in mireds (+ warmer) and towards magenta (+) or green (−). Unlike printer lights, it changes how the film itself is exposed. |
| Red / Green / Blue Layer Contrast | Development gamma per dye layer: the film crossover. 18% grey stays neutral, while shadows and highlights shift in opposite directions. |
| Push Pull | Development in stops. Push is fitted to measured push-processed Portra 800 (gamma ×1.20 at +1, ×1.31 at +2). Pull is the inverse. |
| Negative Contrast | Development gamma around 18% grey. The stock's toe and shoulder are kept. |
| Dye Crossover: Midtone Position, Midtone Hold, Shadow / Highlight / Offset Cyan, Magenta, Yellow | Per-layer exposure shifts in smooth shadow and highlight zones around the midtone, named by the print result (+ Cyan = a more cyan print). Applied before development, so a grey ramp can never reverse. |
| Dye Saturation: Hue Twist, Chroma Rolloff, Vibrance, Richness, Highlight Desaturation | Shapes the colour of the exposure before development: rotation about the neutral axis, a soft limit on strong colours, a boost for weak colours, density build-up in saturated colours, and colour drained from highlights. Greys stay unchanged. |
| Print Exposure | Printer light on all channels, in points (about 12 points = 1 stop) |
| Printer Red / Green / Blue | Lab timing in points. More red light means more cyan, so the print goes cooler. |
| Print Contrast | Print development gamma around 18% grey |
| Film Saturation | Colour separation at exposure onto the negative. 1 is the stock as measured, 0 is black and white. Greys are never changed. |
| Bleach Bypass | Off / Authentic / Grunge. Skip-bleach processing, modelled as retained metallic silver: a spectrally flat density that follows the dye density. |
| Bleach Stage | Print gives desaturated colour, deep blacks and a harder print. Negative gives harder, blown-out highlights. |
| Bleach Strength / Silver Contrast | How much silver is kept, and how strongly it piles into the dense parts |
| Bleach Keeps Mid Grey | Re-times the print so 18% grey keeps its brightness: exact for the negative, within about 1/10 stop for the print |
| Gamut Compress Input | Softly brings colours outside Rec.709 inside before exposure, instead of clipping them |
| Bypass | Return the input unchanged |
| Input Encoding | DaVinci WG Intermediate (default), ACES AP1 ACEScct, Scene Linear Rec709, Rec709 Gamma 2.4, or Negative Cineon Log (prints a negative from another MC Film Core node) |
| Negative Stock / Print Stock | The stocks above |
| White Point | D65 / D60 / D55: the white the projected print is rendered at |
| Output | Rec709 Gamma 2.4 or 2.2, sRGB, P3 D65 Gamma 2.6, Rec2020 Gamma 2.4, DaVinci WG Intermediate (the print kept in DWG, see below), or Negative Cineon Log (the developed negative, for film effects, a second MC Film Core node or a print LUT) |

**Node placement.** The node's output is the projected print, which is display-referred, like a print LUT. Put it last, after your grade, and set Output to match your monitoring. With DaVinci Wide Gamut colour management, set the timeline output so it doesn't apply a second display transform, or use a CST after the node.

**Chaining with other DCTLs: three ways to use it**

```
A. One node (display out)
   [grade] -> [MC Film Core  Output: Rec709 Gamma 2.4]

B. DWG out, for effects that act on the finished print (mist, vignette, gate, weave)
   [grade] -> [MC Film Core  Output: DaVinci WG Intermediate] -> [DWG effects]
           -> [CST  DWG/DI -> Rec.709 Gamma 2.4, tone mapping None, gamut mapping None]

C. Split negative / print, for effects that live on the film (grain per dye layer, halation)
   [grade] -> [MC Film Core  Output: Negative Cineon Log] -> [film effects on the negative]
           -> [MC Film Core  Input: Negative Cineon Log, same Negative Stock] -> display or DWG
```

- **B** is exact: the DWG output plus that CST reproduces the Rec709 output to within 1e-6.
- **C** with no effects in between gives the same result as A, to within 1e-6, bleach bypass included. Set Bleach Bypass on the second (printing) node; the Cineon negative carries the dye densities only.
- C is also how the OFX plugin will be organised internally.

**Install.** Copy the `.dctl` to `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT` (macOS: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`). Then use **Project Settings › Color Management › Update Lists**, and pick it under **ResolveFX Color › DCTL**.

`docs/chart.png` shows a synthetic test chart through seven stock pairs. `docs/features.png` shows the bleach bypass modes, Film Saturation, Dye Crossover and Dye Saturation.

### Tests

`python3 tests/test_film_core.py` compiles the real generated `.dctl` (as C++11 and C99, warnings as errors) and checks it against the Python reference model in `tools/mcfilm_model.py`. It checks:
- 18% grey prints neutral for every pair.
- Grey ramps are monotonic over 16 stops.
- Hue sweeps are continuous.
- Every control acts in the right direction.
- All outputs stay finite for extreme inputs.

### Rebuilding the stock tables

```
python3 tools/build_dctl.py --profiles <spektrafilm>/src/spektrafilm/data/profiles
python3 tools/build_dctl.py          # regenerate the DCTL from data/mcfilm_tables.json
```

Edit `src/MC_Film-Core.dctl.in`, never the generated `.dctl`.

---

## MC Film Grain v0.2 and MC Film Halation v0.2

The full film chain in Resolve:

```
[grade, DWG] -> [MC Film Halation] -> [MC Film Core  Output: Negative Cineon Log]
             -> [MC Film Grain]     -> [MC Film Core  Input: Negative Cineon Log] -> display (or DWG)
```

Use the same Negative Stock on all Core and Grain nodes, and the same Gauge on Grain and Halation. `docs/film_look.png` shows this chain on 250D → 2383 for Super 35, Super 16 and Super 8.

### MC Film Grain (`MC_Film-Grain-v0.2.dctl`), on the Cineon negative
- **Grain model:** each dye layer is a field of real, randomly placed grains, not interpolated noise. It has no lattice, no grid pattern and an exactly known variance.
- **Calibration:** strength follows the stock's RMS granularity, scaled with Selwyn's law to the grain size. It grows with the square root of density. Granularity figures are approximate datasheet-class values per stock.
- **Gauge:** 8mm / Super 8 / 16mm / Super 16 / Super 35 / 65mm, together with the timeline width, sets grain size and strength on screen.
- **Colour:** the grain gets its colour from the dyes, because the print renders it.
- **Controls:**
  - Grain Amount and Grain Size.
  - Grain Colour: 0 is monochrome grain, 1 gives each layer its own grain.
  - Shadow Grain.
  - Grain Seed. A DCTL has no frame number, so keyframe Seed linearly from 0 on the first frame to the number of frames on the last to make the grain move.

### MC Film Halation (`MC_Film-Halation-v0.4.dctl`), before the negative
- **Physics:** light scattered back through the film base re-exposes mainly the red layer, giving the red-orange glow.
- **Redistribution, not addition:** light is moved, not added. An even field is untouched, so the stock's measured response stays calibrated; red light is conserved to within 0.05%.
- **Gauge:** the halo is sized on the film in micrometres, so it grows on smaller gauges.
- **Controls:**
  - Halation Amount, Halation Size.
  - Halation Colour: red to orange.
  - Bloom: neutral emulsion scatter, for a warm-white glow.
  - Highlight Threshold: 0 is physical.
  - Gauge.
  - Size Mode: Matched (default) keeps the on-screen size across gauges and warms small gauges; Physical fixes the halo on the film.
  - Quality: 32 / 64 / 128 / 256 samples, each averaging three pixels.
- **Known DCTL limit:** around very small, very bright lights a wide glow shows some speckle (8mm, 3-pixel light: Best 28%, Ultra 15%). Use Ultra for the final render. The OFX version will use a real multi-pass blur.

### Tests
`python3 tests/test_film_effects.py` (after `tests/test_film_core.py`) runs 32 checks, including:
- Grain: measured RMS equals the calibrated value, zero mean, no grid pattern, gauge, seed and density laws, and no shift of the printed grey.
- Halation: an even field is untouched, light is conserved, the halo colour, gauge scaling and the threshold.
- Both DCTLs match the Python reference (`tools/mcfilm_effects.py`).

## Roadmap (feature parity with the commercial film suites)

The full feature-by-feature status is in `docs/FEATURES.md`.

**DCTLs: colour, per pixel (next)**
- ~~Bleach Bypass~~ (done in Core v0.2)
- Cast & Crossover (crossover, cast, hue twists, skin preserve)
- ~~Film Sat~~ (done in Core v0.2), Tone Core, Curves
- Palette (harmoniser)
- Balance (skin-driven white balance and exposure; reuses the MC Skin Guard qualifier)
- Negative Designer (edit a stock's curves, layer response and dyes)
- Vignette, test-chart generator
- Already done: Hue → MC HSL Editor, Skin Tone → MC Skin Guard

**DCTLs or OFX: spatial**
- ~~Halation~~ (MC Film Halation v0.1), Pro Mist / bloom, chromatic aberration, film resolution / acutance

**OFX only: needs the frame number or multi-pass rendering**
- Grain: the DCTL version is done (MC Film Grain v0.1, animated with a keyframed Seed). The OFX version will animate it per frame by itself.
- Gate weave & breath, dust & specks, film gate (perforations, neighbouring frames), Petzval lens.
- Licence-key activation, Windows (CUDA) and macOS (Metal) builds.
