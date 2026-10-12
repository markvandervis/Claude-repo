# MC Skin Guard v1.0 — User Manual

**MarkCaptures MC Skin Guard** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com
All rights reserved — see `LICENSE.txt`. Personal and commercial grading use is allowed. Redistribution and resale are not.

MC Skin Guard is a DCTL for **DaVinci Resolve Studio**. It finds skin with a soft qualifier around the skin tone line and then gives you:

- **Hue Consolidate**: pulls skin hues towards the skin tone line. Blotchy red patches and green/yellow casts become one even skin hue.
- **Protect Skin**: pulls skin back to a natural hue and saturation in a node *after* your look or LUT. The look stays on everything else.
- **Skin Saturation, Skin Density, Skin Exposure**: tone controls for skin only.
- **Evenness**: smooths colour blotches within the skin. It changes colour only, never detail or texture. It is not a beauty filter.

---

## 1. Installation

1. Copy `MC_Skin-Guard-v1.0.dctl` into Resolve's LUT folder. A subfolder such as `MarkCaptures` is fine.
   - **Windows:** `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT`
   - **macOS:** `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`
   - **Linux:** `/opt/resolve/LUT`
2. In Resolve, open **Project Settings › Color Management** and click **Update Lists**. Restarting Resolve also works.
3. On the Color page, drag **ResolveFX Color › DCTL** from the Effects library onto a node. Pick **MC_Skin-Guard-v1.0** from the *DCTL List*.

DCTLs need **DaVinci Resolve Studio**. The free version does not run them.

---

## 2. Choose the Input Encoding first

Set **Input Encoding** (at the bottom of the panel) to what the node actually receives:

| Your project | Input Encoding |
|---|---|
| DaVinci Wide Gamut colour management, or a CST to DWG / DaVinci Intermediate before the node | **DaVinci WG Intermediate** (default) |
| ACES (ACEScct working space) | **ACES AP1 ACEScct** |
| Cineon film scans | **Cineon Log** |
| Linear EXR / scene-linear Rec.709 | **Scene Linear** |
| Camera log without colour management (any log) | **Log direct** |
| Rec.709 / sRGB display-referred material | **Display Rec.709 sRGB** |

These are the same modes as in the MC HSL Editor. In every mode, skin is *selected* by its hue, saturation and luma in Rec.709, which is where the vectorscope's skin tone line is. In the wide-gamut modes, hue and saturation are changed in Rec.709 through an exact, lossless round trip. Colours outside Rec.709 are never clipped, so the full DaVinci Wide Gamut / AP1 range survives the node. Exposure and Density are true exposure changes in your working encoding.

In **Log direct**, saturation is read from the log values, which look much less saturated. Lower **Skin Sat Low** (to about 3–5) if skin isn't fully selected.

---

## 3. The controls

Resolve always lists sliders first, then the check box, then the combo boxes.

### Global
| Control | What it does |
|---|---|
| **Overall Amount** | Mix between the original (0) and the full result (100). |

### Skin qualifier
| Control | Default | What it does |
|---|---|---|
| **Skin Hue Centre** | 27° | Hue of the skin tone line, in Rec.709 HSV degrees. 27° matches the skin tone indicator on Resolve's vectorscope. Hue Consolidate and Protect Skin pull towards this hue. |
| **Skin Hue Width** | 30° | Width of the fully selected hue range around the centre. At the defaults, skin is fully selected from 12° to 42° and fades out by about −2° and 56°. |
| **Skin Sat Low / High** | 10 / 75 | Saturation band, in percent, that is fully selected. The edges fade in proportion, so pale and deep skin behave alike. Exact greys are never selected, even at Sat Low = 0. |
| **Skin Luma Low / High** | 0 / 100 | Luma band, in percent, that is fully selected. |
| **Qualifier Softness** | 50 | Width of the soft fade at every edge. 0 gives a tight key, 100 a very gentle one. |

Use **Show Skin Mask** while you set these up.

### Hue Consolidate
| Control | What it does |
|---|---|
| **Hue Consolidate** | Pulls every skin hue towards Skin Hue Centre, from both sides. At 100, skin hues move 90 % of the way to the line. Hue order is always kept, so gradients can't tear. 30–60 is a natural range. |
| **Redness** | Adds to (or takes from) Hue Consolidate on the **red/magenta** side only. Use it on its own to remove redness, flushed cheeks or rosacea, and leave yellow-side skin alone. |
| **Yellow Green** | Same, on the **yellow/green** side only. Use it to remove sallow, olive or green casts from bad light. |

### Protect Skin (for a node after the look)
| Control | Default | What it does |
|---|---|---|
| **Protect Skin** | 0 | Pulls skin back towards the skin tone line, and its saturation towards Natural Saturation. |
| **Protect Width** | 40° | Extra hue width for Protect. A look can push skin away from its normal hue, so Protect looks wider than the main qualifier. |
| **Natural Saturation** | 35 | Skin saturation that Protect restores. Washed-out skin is lifted towards it and over-saturated skin calmed towards it. It's kept inside the Skin Sat band. |

### Skin tone
| Control | What it does |
|---|---|
| **Skin Saturation** | Saturation of skin only, from −100 (half the chroma) to +100 (1.5×). Luma is kept. |
| **Skin Density** | Film-like density: the more saturated a skin pixel, the darker it gets (up to about −0.4 stop for typical skin at +100). Negative values lighten saturated skin. |
| **Skin Exposure** | Exposure of skin only, ±1 stop at ±100. Hue and saturation are kept. In the log and linear modes this is an exact exposure change. |

### Evenness
| Control | Default | What it does |
|---|---|---|
| **Evenness** | 0 | Moves each skin pixel's colour towards the average colour of the skin around it. Each pixel's own luma is kept exactly, so pores, texture and sharpness are untouched. Lips, eyes, brows, hair and background are kept out of the average automatically, because they differ too much in colour or brightness. |
| **Evenness Radius** | 8 | Size of the averaging area, in pixels at 1920 wide. It scales with resolution automatically. Small (3–6) evens fine mottling, large (12–32) evens bigger blotches. |

### Check box and combo boxes
| Control | What it does |
|---|---|
| **Bypass** | Returns the input unchanged. |
| **Input Encoding** | See section 2. |
| **Show Skin Mask** | **Mask** shows the skin selection in white. **Isolate** keeps skin in colour and shows everything else as dim grey. Turn it **Off** before rendering. |

---

## 4. Recommended node tree

```
[CST in → DWG/DI] → [Balance / exposure] → [MC Skin Guard: CLEAN] → [Look / LUT / MC HSL Editor] → [MC Skin Guard: PROTECT] → [CST out]
```

1. **MC Skin Guard: CLEAN**, *before* the look, on a balanced image. Use Hue Consolidate / Redness / Yellow Green, Evenness, and Skin Saturation / Density / Exposure. This is where you fix the skin itself.
2. **Look / LUT**, as usual.
3. **MC Skin Guard: PROTECT**, *after* the look. Use only Protect Skin, Protect Width and Natural Saturation, so the look can't wreck the skin (see section 5).

A typical starting point for the CLEAN node is Hue Consolidate 40, Evenness 40, Skin Density 20. Check with Show Skin Mask first.

---

## 5. Protect Skin: the workflow

**The limitation.** A DCTL only ever sees its own node input. A node after the look can't look back at the ungraded image, and a DCTL can't output a key for other nodes to use.

### Recommended: Skin Reference mode (built in)
Natural skin sits in a known place: on the skin tone line, at moderate saturation. Protect Skin uses that as its reference instead of the ungraded image.

1. Add MC Skin Guard as a serial node **after** the look node(s).
2. Set **Show Skin Mask = Mask**. Raise **Protect Width** until the look-shifted skin is selected but the background isn't. Teal-and-orange looks need little; strong green or yellow looks need more. Then set Show Skin Mask back to Off.
3. Raise **Protect Skin** until the skin looks natural again. 40–70 keeps some of the look's flavour on skin, 100 restores it almost completely.
4. Set **Natural Saturation** to taste: about 25–30 for pale or north-European skin, 35–45 for tanned or deeper skin.

Only the skin's hue and saturation are restored. Its brightness, contrast and everything outside skin keep the look.

### Alternative: keep the look off skin with a Resolve key
If you want skin to keep its *exact* pre-look colour, use Resolve's own keying. A DCTL can't do this part.

1. In the node **before** the look, pull a skin key with Resolve's **HSL qualifier**. It helps to judge it with MC Skin Guard's Show Skin Mask in a temporary node.
2. Connect that node's **key output** to the look node's **key input**.
3. In the look node's **Key** palette, **invert** the key input, so the look applies everywhere *except* skin. Lower the key gain to let some of the look through.
4. Optionally, follow it with MC Skin Guard set to a little Protect Skin, to blend the edges.

Check the result with Highlight mode. Some LUT and Color Space Transform setups apply outside the node's key, so confirm it in your own project.

---

## 6. What MC Skin Guard guarantees

- **No tearing, folds or banding.** Every selection edge is a smooth ramp, with no hard thresholds. Where an operator changes the very thing the mask is built from (saturation under a saturation edge, brightness under a luma edge), that edge **widens automatically** just enough to keep gradients in order. That's why the Show Skin Mask edge can soften when you push Skin Saturation, Exposure or Density hard. The hue pulls can never reverse hue order.
- **Greys are never touched.** Exact neutrals come out bit-identical at any setting.
- **All effect controls at 0 means bit-exact output.** The node is a true pass-through until you move an effect control. Moving only the qualifier controls changes nothing either.
- **No clipping.** Wide-gamut values are kept. In Display mode, a [0, 1] input stays within [0, 1].

## 7. Performance

All controls except Evenness are cheap, per-pixel maths. Evenness reads 16 neighbouring pixels for each skin pixel; non-skin pixels skip this. If playback slows down, keep Evenness at 0 while you grade other things, or cache the node.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| The DCTL doesn't appear | Check that the file is in the LUT folder, then use *Update Lists* or restart Resolve. |
| "wrong argument … in Transform DCTL" | The `transform(...)` line was edited or wrapped. It must stay on a single line. |
| Error on the `DEFINE_UI_TOOLTIP` lines | Your Resolve version predates DCTL tooltips. Delete the `DEFINE_UI_TOOLTIP` lines; they only add hover help. |
| Skin isn't selected | Check Input Encoding first, then Show Skin Mask. In Log direct, lower Skin Sat Low. |
| Lips or background get caught | Narrow Skin Hue Width, raise Skin Sat Low, or lower Qualifier Softness. |
| The effect looks stepped | Turn Show Skin Mask off. Its Isolate mode is a preview only. |

---

## 9. For developers / the OFX port

`tests/` contains:

- `skin_guard_reference.py`: a line-by-line Python mirror of the colour maths.
- `test_skin_guard.py`: the test suite.
- `sg_shim.h`, `sg_harness.cpp`, `sg_c_check.c`, `build.sh`: they compile the **real** `.dctl` on a normal computer (as C++11 and as C99) so it can be tested without Resolve.

Run it with `python3 tests/test_skin_guard.py` (needs g++/gcc and numpy).

In the DCTL, the colour maths (sections 1–3, ending in `SgSkinGuardPixel`) uses no UI variables or texture access. An OFX port can reuse it unchanged and replace only section 4: image access and the slider → argument conversion in `transform()`.
