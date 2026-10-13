# MC Film: gauge presets

## Halation per gauge (MC Film Halation v0.6)

In **Size Mode: Matched** (the default), switching **Gauge** gives the behaviour below by itself. The slider values stay the same; the gauge scales them inside, like the commercial plugins do:
- the glow keeps about the same size on screen and grows slightly on smaller gauges,
- it gets **stronger** on smaller gauges: Halation and Bloom scale with the enlargement to the power 0.6, so 16mm 1.7×, Super 8 2.4× and 8mm 2.7× the 35mm glow (measured from halation-only reference screenshots of the same tubes on all four gauges),
- and slightly warmer on smaller gauges.

**v0.6 glow shape.** The kernel is a disc with a soft edge, fitted to an 8mm headlight reference: a smooth, round, warm-white glow whose red part (halation) reaches 1.35× further than the neutral part (bloom), which gives it a slightly redder rim. The earlier exponential kernel had a sharp peak and a long faint tail, so it looked small and speckled.

Defaults: Halation Amount 0.10, Halation Size 1.0, Halation Colour 0.6, Bloom 0.35, Highlight Threshold 1.0, Quality Best 128. Use Ultra 256 for the final render.

The same presets in **Physical** mode (the halo fixed on the film), written out by hand:

| Preset | Gauge | Size Mode | Halation Amount | Halation Size | Halation Colour | Bloom |
|---|---|---|---|---|---|---|
| **35mm** | Super 35 | Physical | 0.10 | 1.00 | 0.60 | 0.35 |
| **16mm** | 16mm | Physical | 0.17 | 0.44 | 0.52 | 0.59 |
| **Super 8** | Super 8 | Physical | 0.24 | 0.26 | 0.47 | 0.84 |
| **8mm** | 8mm | Physical | 0.27 | 0.22 | 0.45 | 0.94 |

The absolute strength is a first estimate. It was fitted on display-referred screenshots, where the brightest part of the lights is clipped. It will be fine-tuned against the reference at strength 20 on 8mm.

Notes:
- **Colour:** the reference glow is almost white with a warm tint. Physical halation alone is red-orange, because it re-exposes only the red layer. The white part is emulsion scatter: **Bloom**.
- **Smoothness:** the compact soft-disc kernel of v0.6 is sampled densely enough for a smooth glow even around small lights. The OFX version will use a real multi-pass blur.
- **Grain:** set the same Gauge on MC Film Grain. Grain stays physical: it gets bigger and stronger on smaller gauges, as it does on real film.
- **Saving:** a DCTL can't store presets itself. Save each one as a PowerGrade still in the Gallery (right-click the viewer → Grab Still, keep it in a PowerGrade album), or as a ResolveFX preset if your Resolve version offers it in the effect's menu.
- **OFX plugin:** Halation will follow the negative's Film Format automatically, with these values as the defaults per gauge, plus a "Physical" option where the halo keeps a fixed size on the film.
