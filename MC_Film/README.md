# MC Film

**MarkCaptures MC Film** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

MC Film is a film emulation suite for DaVinci Resolve Studio. It starts as DCTLs and becomes an OFX plugin later. The colour maths is written once, so each DCTL is a straight port target for the plugin.

Stock data: derived from **spektrafilm by Andrea Volpato** (https://github.com/andreavolpato/spektrafilm), licensed **CC BY-SA 4.0**. See `LICENSE.txt` and `data/CHANGELOG.txt`. The film engine itself is an independent implementation; no spektrafilm code is used.

---

## MC Film Negative, MC Film Print and MC Film Core v0.6

The film engine comes as three DCTLs built from one source:

| DCTL | What it does |
|---|---|
| `MC_Film-Negative-v0.6.dctl` | Scene → developed negative (Cineon log). Stock categories, exposure, development, Negative Contrast, Dye Crossover, Dye Saturation. |
| `MC_Film-Print-v0.6.dctl` | Negative → projected print. Also **Print Only**: prints the graded image straight onto 2383 / 2393 / a paper, with no negative stock. |
| `MC_Film-Core-v0.6.dctl` | Both in one node, for a quick look. |

The OFX plugin will be the combination of these, in the same order.

### Node tree

```
Full film chain
  [grade, DWG] -> [MC Film Halation] -> [MC Film Negative] -> [MC Film Grain] -> [MC Film Print] -> display
                                       (Cineon out)                             (Input: Negative Cineon Log)

Print only (no negative)
  [grade, DWG] -> [MC Film Print  Input: DaVinci WG Intermediate (Print Only)]

Further DWG effects after the print
  ... -> [MC Film Print  Output: DaVinci WG Intermediate] -> [DWG effects]
      -> [CST  DWG/DI -> Rec.709 Gamma 2.4, tone mapping None, gamut mapping None]
```

- Set the same negative on MC Film Negative, MC Film Grain and MC Film Print (Negative Stock).
- Negative → Print gives the same picture as Core in one node (tested to 1e-5, the rounding of the Cineon link).
- The print is display-referred, like a print LUT: put MC Film Print last. In a DWG colour-managed project, make sure the timeline doesn't add a second display transform, or use the DWG output and a CST.

### How it works

1. **Exposure onto the negative.** The Mallett & Yuksel 2019 spectral basis, lit by the stock's reference light, against the stock's measured layer sensitivities.
2. **Development.** Each layer's measured characteristic curve, with Exposure, Push/Pull, Contrast and the rest of the Negative Contrast section.
3. **Printing.** A 41-band spectral calculation: printer lamp × the negative's measured dyes and orange mask × the print stock's layer sensitivities, in Kodak printer points (1 point = 0.025 log E).
4. **Print development and projection.** The print stock's measured curves, its dyes under the viewing light (xenon projector for 2383 / 2393, D50 for papers), CIE 1931 observer, adapted to the chosen white.

Each negative and print pair is timed so that a scene 18% grey prints as a neutral grey at the laboratory aim density (1.0).

### Stocks

| Stock Category | Negatives |
|---|---|
| Kodak Vision3 | 50D, 250D, 200T, 500T |
| Kodak Verita | Verita 200D |
| Kodak Photo | Portra 160, 400, 800, Ektar 100, Gold 200, Ultramax 400 |
| Fujifilm Photo | Pro 400H, C200, Xtra 400 |

Prints: Kodak 2383, 2393, Portra Endura, Endura Premier, Supra Endura, Ultra Endura, Ektacolor Edge, Fujifilm Crystal Archive.

Vision2 and Vision1 are not in the list yet: the stock data we use has no measurements for them, and we don't invent data under a real stock name. They can be added from Kodak's published datasheets (see the roadmap).

### MC Film Negative controls

| Control | What it does |
|---|---|
| Stock Category + Kodak Vision3 / Kodak Verita / Kodak Photo / Fujifilm Photo | The negative. Only the list of the chosen category counts. |
| Exposure, Push Pull | Camera exposure in stops; development (push fitted to measured Portra 800 push-processing, pull is the inverse) |
| Scene Temp / Scene Tint | White balance of the scene before the film, in mireds and towards magenta (+) / green (−) |
| Red / Green / Blue Layer Contrast | Development gamma per dye layer: the film crossover |
| **Negative Contrast:** Contrast Preset | None (Stock) / Soft / Natural / Punchy / Hard: a starting point; the sliders act on top of it |
| Contrast | Development gamma around 18% grey, × the preset's |
| Open Close | + flattens shadows and highlights (more latitude), − steepens them; 18% grey stays |
| Shadow Roll, Black Depth | Stops below grey where the shadows roll off, and how many stops they still have after it (12 = off) |
| Highlight Roll, Highlight Latitude | Stops above grey where the highlights roll off, and how many stops they still have after it (12 = off) |
| Black Anchor, White Anchor | Moves the print's black and white ends (+ deeper blacks / brighter whites) |
| Base Fog | Flashes the negative with a little even light: lifted, milky blacks |
| Show Curve | Draws the negative's curves (red, green, blue layers, the stock's own curve in grey) in the top left of the frame |
| **Dye Crossover:** Midtone Position, Midtone Hold, Shadow / Highlight / Offset Cyan, Magenta, Yellow | Per-layer exposure shifts in shadow and highlight zones, named by the print result |
| **Dye Saturation:** Color Response | Colour separation at exposure (1 = the stock, 0 = black and white) |
| Hue Twist, Chroma Rolloff, Vibrance, Richness, Highlight Desaturation | Rotation about the neutral axis, a soft limit on strong colours, a boost for weak colours, density in saturated colours, colour drained from highlights |
| Color Weight | How Color Response changes brightness: 1 spreads the layers evenly (as measured), 0 weights them by how much each drives the print brightness, so saturation changes brightness less (about a third less on Kodak stocks) |
| Rendering | Natural (the stock) or Vivid (more separation and dye density) |
| Gamut Compress Input, Input Encoding, Bypass | As before: DWG (default), ACEScct, Scene Linear Rec709, Rec709 Gamma 2.4 |

All Negative Contrast controls keep 18% grey exactly where it is, so the print stays timed, and none of them can make a grey ramp reverse.

### MC Film Print controls

| Control | What it does |
|---|---|
| Input | Negative Cineon Log (from MC Film Negative), or a Print Only input: DWG, ACEScct, Scene Linear, Rec709 |
| Negative Stock | The negative being printed (same as on MC Film Negative). Not used for Print Only. |
| Print Stock, White Point (D65 / D60 / D55) | The print, and the white it is rendered at |
| Print Exposure, Printer Red / Green / Blue | Printer lights in points (about 12 points = 1 stop). More red light = a cooler print. |
| Print Contrast | Print development gamma around 18% grey |
| Bleach Bypass, Bleach Stage, Bleach Strength, Silver Contrast, Bleach Keeps Mid Grey | Skip-bleach at the print or the negative, as retained silver |
| Output | Rec709 Gamma 2.4 / 2.2, sRGB, P3 D65 Gamma 2.6, Rec2020 Gamma 2.4, DaVinci WG Intermediate |

**Print Only** prints through an ideal negative: each channel exposes one print layer through a straight-line negative with the average printing contrast of the Vision3 stocks, with no colour crosstalk and no toe or shoulder. 18% grey prints neutral at the same level as through a real negative.

**Install.** Copy the `.dctl` files to `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT` (macOS: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`), then **Project Settings › Color Management › Update Lists**, and pick them under **ResolveFX Color › DCTL**.

### Tests

`python3 tests/test_film_core.py` and `python3 tests/test_film_split.py` compile the real generated DCTLs (as C++11 and C99, warnings as errors) and check them against the Python reference model in `tools/mcfilm_model.py`. They check:
- Negative → Print equals Core, for every stock in every category.
- The Negative Contrast controls never move 18% grey and never reverse a grey ramp; every control acts in the right direction.
- Print Only prints 18% grey neutral on every print stock.
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

Edit `src/MC_Film-Core.dctl.in` (one template for Core, Negative and Print), never the generated `.dctl` files.

---

## MC Film Grain v0.3 and MC Film Halation v0.6

They sit in the full film chain shown above (Halation before MC Film Negative, Grain between Negative and Print). Use the same Negative Stock on Negative, Grain and Print, and the same Gauge on Grain and Halation. `docs/film_look.png` shows this chain on 250D → 2383 for Super 35, Super 16 and Super 8.

### MC Film Grain (`MC_Film-Grain-v0.3.dctl`), on the Cineon negative
- **Grain model:** each dye layer is a field of real, randomly placed grains, not interpolated noise. It has no lattice, no grid pattern and an exactly known variance.
- **Calibration:** strength follows the stock's RMS granularity, scaled with Selwyn's law to the grain size. It grows with the square root of density. Granularity figures are approximate datasheet-class values per stock.
- **Gauge:** 8mm / Super 8 / 16mm / Super 16 / Super 35 / 65mm, together with the timeline width, sets grain size and strength on screen.
- **Colour:** the grain gets its colour from the dyes, because the print renders it.
- **Controls:**
  - Grain Amount and Grain Size.
  - Grain Colour: 0 is monochrome grain, 1 gives each layer its own grain.
  - Shadow Grain.
  - Grain Seed. A DCTL has no frame number, so keyframe Seed linearly from 0 on the first frame to the number of frames on the last to make the grain move.

### MC Film Halation (`MC_Film-Halation-v0.6.dctl`), before the negative
- **Physics:** light scattered back through the film base re-exposes mainly the red layer, giving the red-orange glow.
- **A glow that only adds (v0.5):** each pixel gets the light arriving from brighter neighbours. No channel ever goes down, so the centre of a light keeps its colour at any setting (v0.4 could turn cores cyan on small gauges). An even area such as a sky is left as it is, so the stock's measured response stays calibrated.
- **Glow shape (v0.6):** a disc with a soft edge, fitted to a reference 8mm headlight. Warm-white, with the red halation reaching a little further than the neutral bloom.
- **Gauge:** the halo is sized on the film in micrometres, so it grows on smaller gauges.
- **Controls:**
  - Halation Amount, Halation Size.
  - Halation Colour: red to orange.
  - Bloom: neutral emulsion scatter, for a warm-white glow.
  - Highlight Threshold: stops above 18% grey where the glow starts (default 1). Everything below is untouched; 0 is physical but lets the image noise glow into a faint haze.
  - Gauge.
  - Size Mode: Matched (default) keeps the on-screen size across gauges and makes small gauges stronger and warmer; Physical fixes the halo on the film.
  - Quality: 32 / 64 / 128 / 256 samples, each averaging three pixels.
- **Quality:** Best 128 is smooth for normal use; use Ultra for the final render. The OFX version will use a real multi-pass blur.

### Tests
`python3 tests/test_film_effects.py` (after `tests/test_film_core.py`) runs 32 checks, including:
- Grain: measured RMS equals the calibrated value, zero mean, no grid pattern, gauge, seed and density laws, and no shift of the printed grey.
- Halation: an even field is untouched, nothing ever darkens, no cyan cores on any gauge, the halo colour, gauge scaling and the threshold.
- Both DCTLs match the Python reference (`tools/mcfilm_effects.py`).

## MC Pro Split v0.6 (RGB split tone, five zones)

`MC_Pro-Split-v0.6.dctl` is an RGB split tone: a red, green and blue offset for each of five tonal zones, Hi, Hi-Mid, Mid, Lo-Mid and Lo. It is made to sit in a PowerGrade, and it will be part of the OFX plugin.

**PowerGrade order (DaVinci Wide Gamut):**

```
[camera log, e.g. S-Log3] -> [CST to DaVinci Wide Gamut / DaVinci Intermediate] -> [corrections]
  -> [MC Pro Split  Transfer Function: DaVinci Intermediate]
  -> [CST DaVinci Wide Gamut / Intermediate -> Rec.709 Gamma 2.4]
```

It works directly on the log code values of the chosen **Transfer Function**, in the image's own gamut, so each offset is an exposure shift of that channel. The transfer function sets middle grey (TF(0.18)) and the size of a stop, so the zones land in the same place whatever the log curve.

The five zones are broad and overlap. They lie between four soft boundaries at ±0.6 and ±1.9 stops from the Pivot. The weights always add up to 1, so the same setting on all five zones is one plain offset. With every zone at 0, the node returns its input unchanged, bit for bit. A grey ramp doesn't reverse for any single zone at ±100, any mix within ±50, or neighbouring zones at opposite ±100.

**Matched to the reference.** Zone width and strength, and the way Clean Blacks works, were fitted to curve measurements of a reference RGB split tone: Lo Red −100 at Clean Blacks 30, 51, 67 and 100, and a five-zone setting with Neutral Pivot 31.8. Ours matches the Lo zone within about 0.007 code value, and the Neutral Pivot band and shadow side of the five-zone setting closely.
- **Lo at −100:** about 1.3 stops at its peak, still a little over half of that at middle grey, and fading out above +2.5 stops.
- **Clean Blacks:** sets *how far up from black* the toning is faded out: 100 is clean up to about 5 stops above grey, 50 about 3 stops above black. Black itself always stays neutral.
- **Not matched yet:** the reference Hi zone keeps growing towards white, while ours levels off above about +3 stops. Lo-Mid, Mid and Hi-Mid have not been measured on their own.

| Control | What it does |
|---|---|
| Hi / Hi-Mid / Mid / Lo-Mid / Lo Red, Green, Blue | Offset per channel per zone, −100 to +100 (Lo / Hi at 100 ≈ 1.3–1.8 stops towards the ends, the inner zones ≈ 0.4 stop at their centre) |
| Blend | Strength of the whole split tone, in % |
| Pivot | Centre of the Mid zone in stops from middle grey; all zones move with it |
| Neutral Pivot | Keeps a band around the Pivot neutral; the higher, the wider (31.8 fades back in over about 2 stops either side) |
| Clean Blacks / Clean Whites | How far up from black / down from the top of the range (code 1.0) the toning is faded out (default 30) |
| Sat Mask | Keeps the toning off saturated colours, in % |
| Show Curves | Red, green and blue curves of a grey ramp over the whole frame and the middle grey line. The lines are see-through and add up: unchanged they form one white line, pulling red down leaves cyan + red |
| Highlight Sat Mask | The picture in grey, with the colours Sat Mask keeps out painted magenta |
| Show Ramp | A toned grey ramp along the bottom of the frame |
| Transfer Function | DaVinci Intermediate (default), ACEScct, ARRI LogC3, ARRI LogC4, Sony S-Log3, Panasonic V-Log, Canon Log 3, RED Log3G10, Cineon Log, Scene Linear |

`docs/prosplit.png` shows a test chart before and after, and with Show Curves on. `python3 tests/test_prosplit.py` checks it (55 checks):
- Identity at defaults for every transfer function, and DCTL == reference for every transfer function.
- Grey ramps never reverse for extreme and random zone settings.
- Every zone acts only where it should, and every control and view acts in the right direction.

## Roadmap (feature parity with the commercial film suites)

The full feature-by-feature status is in `docs/FEATURES.md`.

**DCTLs: colour, per pixel (next)**
- ~~Bleach Bypass~~ (done in Core v0.2)
- ~~Cast & Crossover~~ (done: MC Pro Split v0.6, an RGB split tone in five zones)
- ~~Film Sat~~ (done in Core v0.2), Tone Core, Curves
- Palette (harmoniser)
- Balance (skin-driven white balance and exposure; reuses the MC Skin Guard qualifier)
- ~~Negative Contrast~~ (done in v0.6). Next: editing a stock's layer response and dyes.
- Vision2 / Vision1 stocks, digitised from Kodak's published datasheets.
- Vignette, test-chart generator
- Already done: Hue → MC HSL Editor, Skin Tone → MC Skin Guard

**DCTLs or OFX: spatial**
- ~~Halation~~ (MC Film Halation v0.1), Pro Mist / bloom, chromatic aberration, film resolution / acutance

**OFX only: needs the frame number or multi-pass rendering**
- Grain: the DCTL version is done (MC Film Grain v0.1, animated with a keyframed Seed). The OFX version will animate it per frame by itself.
- Gate weave & breath, dust & specks, film gate (perforations, neighbouring frames), Petzval lens.
- Licence-key activation, Windows (CUDA) and macOS (Metal) builds.
