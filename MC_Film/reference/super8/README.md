# Super 8 reference: Mark's own scans

**MarkCaptures MC Film** · © 2026 Mark van der Vis / MarkCaptures · www.markcaptures.com

Four frames from Mark's own Super 8 footage, scanned with the full frame and perforation visible. The film is a Kodak colour **reversal** (positive, projectable) stock, not a negative. These are the reference for the MC Film **Super 8** look: grain, halation and overall image character.

| File | Scene | Useful for |
|---|---|---|
| `s8_sign.webp` | Road sign, trees, bright sky | Grain in a flat sky; colour of reds/blues; blacks; an edge light leak (right) |
| `s8_street_sun.webp` | Brick street at sunset, sun on the windows | **Halation** on sunlit windows; deep shadows |
| `s8_ski.webp` | Skiers, snow, low sun | **Halation** around a sun glint; flat sky grain; low-contrast flare |
| `s8_pool.webp` | Pool from above, saturated inflatables | Saturated colours; soft image; deep blacks |

The files are screenshots of the Resolve viewer (about 1650 px across the picture area), saved as WebP. Measurements below are in display values (0–1) and in fractions of the **picture width**, so they don't depend on the screenshot size.

## What the measurements say

### Halation

**Sun glint, `s8_ski`** (centre x 1231, y 519). Glow above the local background (0.42), per channel, by distance from the centre:

| radius (px) | 0 | 6 | 10 | 13 | 16 | 20 | 25 |
|---|---|---|---|---|---|---|---|
| R | 0.41 | 0.35 | 0.24 | 0.16 | 0.10 | 0.04 | 0.02 |
| G | 0.39 | 0.29 | 0.17 | 0.10 | 0.05 | 0.01 | 0.01 |
| B | 0.38 | 0.28 | 0.15 | 0.08 | 0.03 | 0.00 | 0.01 |

- **Red reaches further than green and blue,** the signature of halation (light scattered back through the base exposes the red layer). The red glow lasts to about **20–25 px (≈1.2–1.5 % of the picture width)**. Green and blue fade by about 13–16 px (≈0.9 %).
- **The colour shifts outwards:** R : G : B ≈ 1 : 0.62 : 0.48 at 13 px and 1 : 0.47 : 0.27 at 16 px. So it's orange near the core and redder at the rim.
- The core is a soft, cream-white disc, not a hard point. The highlight never clips to pure white (0.83).

**Sunlit windows, `s8_street_sun`.** The bright windows are cream-yellow (about 0.82 / 0.81 / 0.73) and never reach white. Every edge into the dark brick has a **warm amber fringe 5–8 px wide (≈0.3–0.5 % of width)**: red leads, blue lags, e.g. 0.48 / 0.42 / 0.30 at the edge. This is the tight, warm halation that makes sunlit Super 8 look golden.

### Tone and colour

| Frame | Brightest whites | Darkest blacks |
|---|---|---|
| sign | 0.78 / 0.86 / 0.87 | 0.01 / 0.06 / 0.04 (teal-green) |
| street | 0.84 / 0.86 / 0.85 | 0.06 / 0.06 / 0.07 |
| ski | 0.69 / 0.66 / 0.67 (flare) | 0.10 / 0.10 / 0.13 |
| pool | 0.84 / 0.84 / 0.83 | 0.01 / 0.01 / 0.01 |

- **Highlights top out at about 0.84–0.87** and roll off, as a projected reversal print does. Nothing reaches 1.0.
- **Blacks are deep** but can carry a teal-green cast. Against the light (ski) they flare up to about 0.10.
- **Colour:** dense, saturated primaries (red signs, blue loungers, magenta and yellow inflatables). Skies are cyan-blue, greens lean yellow, highlights are warm cream.
- **Sharpness:** soft overall. Fine detail is about half that of a modern digital frame at the same size, a mix of the Super 8 lens, the small frame and the scan.

### Grain

The WebP screenshots have removed most of the fine grain. In the flat skies, what's left is only about 1/255 per channel, with the channels about 55 % correlated. So the grain **can't be measured reliably from these files**. What can still be seen:

- It's **clumpy and soft**, not pixel-sharp: clumps several pixels across at this size.
- It's partly coloured (channels only about half correlated).
- It's stronger in the shadows and mid-shadows than in the bright sky.

**Needed to calibrate the grain:** two or three frames exported from Resolve as **PNG or TIFF at 100 % (no viewer scaling, no WebP/JPEG)**, ideally including a flat sky or wall, plus the scan resolution.

## Suggested MC Film settings for this look (until calibrated)

| DCTL | Setting | Why |
|---|---|---|
| Halation | Gauge **Super 8**, Size Mode **Matched**, **Halation Size ≈ 2.0** | Matched Super 8 at Size 1 makes the bloom ≈0.45 % of the width and the red rim ≈0.6 %. The reference is about 0.9 % and 1.3 %. |
| Halation | Halation Colour ≈ 0.45–0.5 | Orange near the core and redder at the rim, rather than pure red. |
| Halation | Highlight Threshold ≈ 1.0–1.5 stops | Glow only on the sun, sky and windows, as in the scans. |
| Grain | Gauge **Super 8** | Start point; amount and size to be set from lossless frames. |
| Print / tone | A shoulder that caps whites around 0.85, and slightly lifted teal-green blacks | Matches the reversal projection look. |

The red light leak on the right edge of `s8_sign` is edge fog from loading the cartridge, not halation. It could become its own effect later.
