# MC Film: gauge presets

## Halation per gauge (MC Film Halation v0.5)

**From v0.3 these presets are automatic.** In **Size Mode: Matched** (the default), switching **Gauge** gives the behaviour below by itself:
- the glow keeps about the same size on screen and grows slightly on smaller gauges,
- it gets **stronger** on smaller gauges: Halation Amount scales with the enlargement to the power 0.6, so 16mm 1.7×, Super 8 2.4× and 8mm 2.7× the 35mm glow (measured from halation-only screenshots of the same tubes on all four gauges),
- and slightly warmer on smaller gauges,
- **Bloom** (default 0.25) adds the neutral emulsion scatter that makes the glow warm-white instead of deep red.

Defaults: Halation Amount 0.25, Halation Size 1.0, Halation Colour 0.6, Bloom 0.25, Highlight Threshold 2.0, Quality Best 128. Bloom is not scaled by the gauge (v0.5). Use Ultra 256 for the final render.

The table gives the equivalent **Physical**-mode settings (the halo fixed on the film), which are the same presets written out by hand. They were calibrated by measuring the glow around a fluorescent tube in matched reference screenshots (strength 20 at 8mm, Super 8, 16mm and 35mm), then simulating the same tube through MC Film Halation and MC Film Core (250D → 2383) at 1920 px:

| Preset | Gauge | Size Mode | Halation Amount | Halation Size | Halation Colour |
|---|---|---|---|---|---|
| **35mm** | Super 35 | Physical | 0.25 | 2.00 | 0.60 |
| **16mm** | 16mm | Physical | 0.26 | 0.86 | 0.55 |
| **Super 8** | Super 8 | Physical | 0.28 | 0.50 | 0.50 |
| **8mm** | 8mm | Physical | 0.30 | 0.43 | 0.45 |

Measured result (glow width at 10% / 3% of peak, in the screenshots' 34% preview pixels, and glow green share):

| | 35mm | 16mm | Super 8 | 8mm |
|---|---|---|---|---|
| Reference screenshots | 27 / 32 | 25 / 30 | 28 / 33 | 28 / 33 |
| MC Film presets | 18.5 / 25.1 | 18.5 / 25.7 | 19.1 / 26.8 | 20.2 / 27.3 |
| Glow green share (higher = whiter) | 0.48 | 0.45 | 0.43 | 0.41 |

Notes:
- **Colour:** the reference glow is almost white with a warm tint. Physical halation alone is red-orange, because it re-exposes only the red layer. The white part is emulsion scatter, which v0.3 adds as **Bloom**.
- **Speckle:** around very small, very bright lights (headlights, bulbs) a single-pass DCTL can't make a wide glow perfectly smooth. Measured on 8mm around a 3-pixel light: Good 97%, Best 28%, Ultra 15% variation. Use Ultra for the final render. The OFX version will use a multi-pass blur and be clean.
- **Grain:** set the same Gauge on MC Film Grain. Grain stays physical: it gets bigger and stronger on smaller gauges, as it does on real film.
- **Saving:** a DCTL can't store presets itself. Save each one as a PowerGrade still in the Gallery (right-click the viewer → Grab Still, keep it in a PowerGrade album), or as a ResolveFX preset if your Resolve version offers it in the effect's menu.
- **OFX plugin:** Halation will follow the negative's Film Format automatically, with these values as the defaults per gauge, plus a "Physical" option where the halo keeps a fixed size on the film.
