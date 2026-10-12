# MC Film

**MarkCaptures MC Film** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

MC Film is a film emulation suite for DaVinci Resolve Studio. It starts as DCTLs and becomes an OFX plugin later. The colour maths is written once, so each DCTL is a straight port target for the plugin.

Stock data: derived from **spektrafilm by Andrea Volpato** (https://github.com/andreavolpato/spektrafilm), licensed **CC BY-SA 4.0**. See `LICENSE.txt` and `data/CHANGELOG.txt`. The film engine itself is an independent implementation; no spektrafilm code is used.

---

## MC Film Core v0.3: negative + print engine

`MC_Film-Core-v0.3.dctl`

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
| Push Pull | Development in stops. Push is fitted to measured push-processed Portra 800 (gamma ×1.20 at +1, ×1.31 at +2). Pull is the inverse. |
| Negative Contrast | Development gamma around 18% grey. The stock's toe and shoulder are kept. |
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
| Output | Rec709 Gamma 2.4, sRGB, P3 D65 Gamma 2.6, Rec2020 Gamma 2.4, DaVinci WG Intermediate (the print kept in DWG, see below), or Negative Cineon Log (the developed negative, for film effects, a second MC Film Core node or a print LUT) |

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

`docs/chart.png` shows a synthetic test chart through seven stock pairs. `docs/features.png` shows the bleach bypass modes and Film Saturation.

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

## Roadmap (feature parity with the commercial film suites)

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
- Halation (gauge-dependent), Pro Mist / bloom, chromatic aberration, film resolution / acutance

**OFX only: needs the frame number or multi-pass rendering**
- Grain grown per dye layer and scaled by gauge (8 / 16 / 35 mm). It must change every frame, and a DCTL has no frame number.
- Gate weave & breath, dust & specks, film gate (perforations, neighbouring frames), Petzval lens.
- Licence-key activation, Windows (CUDA) and macOS (Metal) builds.
