# MC Film: gauge presets

## Halation per gauge (MC Film Halation v0.2)

These presets reproduce the gauge behaviour of current commercial film plugins:
- **Size:** the glow stays about the same size on screen and grows slightly on smaller gauges.
- **Colour:** it gets warmer as the gauge gets smaller.

They were calibrated by measuring the glow around a fluorescent tube in matched screenshots (strength 20 at 8mm, Super 8, 16mm and 35mm), then simulating the same tube through MC Film Halation and MC Film Core (250D → 2383) at 1920 px.

| Preset | Gauge | Halation Amount | Halation Size | Halation Colour | Highlight Threshold | Quality |
|---|---|---|---|---|---|---|
| **35mm** | Super 35 | 0.25 | 2.00 | 0.60 | 0 | Good 64 |
| **16mm** | 16mm | 0.26 | 0.86 | 0.55 | 0 | Good 64 |
| **Super 8** | Super 8 | 0.28 | 0.50 | 0.50 | 0 | Best 128 |
| **8mm** | 8mm | 0.30 | 0.43 | 0.45 | 0 | Best 128 |

Measured result (glow width at 10% / 3% of peak, in the screenshots' 34% preview pixels, and glow green share):

| | 35mm | 16mm | Super 8 | 8mm |
|---|---|---|---|---|
| Reference screenshots | 27 / 32 | 25 / 30 | 28 / 33 | 28 / 33 |
| MC Film presets | 18.5 / 25.1 | 18.5 / 25.7 | 19.1 / 26.8 | 20.2 / 27.3 |
| Glow green share (higher = whiter) | 0.48 | 0.45 | 0.43 | 0.41 |

Notes:
- **Colour difference:** the reference glow is almost white with a warm tint, while ours is red-orange: physical halation re-exposes the red layer. Most of the white part of their glow is emulsion scatter (irradiation, "bloom"), which MC Film doesn't have yet. When that's added, the glow will whiten and these presets will be re-tuned.
- **Grain:** set the same Gauge on MC Film Grain. Grain stays physical: it gets bigger and stronger on smaller gauges, as it does on real film.
- **Saving:** a DCTL can't store presets itself. Save each one as a PowerGrade still in the Gallery (right-click the viewer → Grab Still, keep it in a PowerGrade album), or as a ResolveFX preset if your Resolve version offers it in the effect's menu.
- **OFX plugin:** Halation will follow the negative's Film Format automatically, with these values as the defaults per gauge, plus a "Physical" option where the halo keeps a fixed size on the film.
