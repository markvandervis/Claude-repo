# MC Film: feature map

The functionality a professional film-emulation suite needs, using the current commercial plugins (EMBR among them) as a functional reference: what exists, not how it's built. For each feature this lists where it lives in MC Film and its status. "OFX" means it needs the plugin, because it needs file access, the frame number, multi-pass rendering or a custom UI.

Status: ✅ done · 🟡 partly / approximation · ⏳ planned · 🚫 not possible honestly

## Input / output
| Feature | MC Film | Status |
|---|---|---|
| Input colour space (DWG, ACEScct, linear, Rec709) | Negative / Print · Input Encoding | ✅ |
| Output Rec709 2.4 / 2.2, sRGB, P3 2.6, Rec2020 | Negative / Print · Output | ✅ (2.2 added in v0.4) |
| Output Cineon (negative out) | Negative / Print · Output Negative Cineon Log | ✅ |
| Output DWG | Negative / Print · Output DaVinci WG Intermediate | ✅ |
| White point D65 / D60 / D55 | Negative / Print · White Point | ✅ v0.4 |
| Presets / Looks | OFX preset browser; meanwhile Resolve PowerGrades | ⏳ OFX |
| Export LUT (.cube) | Offline export tool from the reference model, then in OFX. Exported LUTs carry the CC BY-SA stock-data notice. | ⏳ |

## Negative
| Feature | MC Film | Status |
|---|---|---|
| Film stock library | Negative · 14 negatives from measured data, in Stock Categories (Kodak Vision3, Kodak Verita, Kodak Photo, Fujifilm Photo) | ✅ v0.6 |
| Vision2 / Vision1 | Needs measured data: to be digitised from Kodak's published datasheets | ⏳ |
| Film format 8mm / Super 8 / 16 / Super 16 / 35 / 65 | Grain + Halation · Gauge (gauge presets: docs/PRESETS.md) | ✅ |
| Film speed / Auto (stock) | Grain uses each stock's granularity, which is "Auto". A manual speed override goes into Grain. | 🟡 |
| Strength (mix) | OFX global mix. In DCTL, use node Key Output gain. | ⏳ |
| Print only (a print stock without a negative) | Print · Print Only inputs, through an ideal negative | ✅ v0.6 |
| Exposure, Push / Pull | Core | ✅ |
| Scene Temp / Tint | Core v0.4 | ✅ |
| Negative saturation | Negative · Color Response | ✅ |
| Rendering Natural / Vivid | Negative · Rendering | ✅ v0.6 |
| Contrast / contrast presets | Negative · Contrast Preset (None, Soft, Natural, Punchy, Hard) + Contrast | ✅ v0.6 |
| Layer gammas / dye crossover | Core v0.4 · Red / Green / Blue Layer Contrast | ✅ |
| Open / Close, Shadow & Highlight roll, Black / White anchor, Highlight latitude, Black depth, Base fog | Negative · Negative Contrast section | ✅ v0.6 |
| Show Curve | Negative · Show Curve (curves drawn over the frame) | ✅ v0.6 |
| Preview Neutral, Dye Crossover Show Curves | Planned | ⏳ |
| Dye crossover: midtone position / hold, shadow / highlight / offset C M Y | Core v0.5 · Dye Crossover | ✅ |
| Dye saturation: colour response, hue twist, chroma rolloff, colour weight, vibrance, richness, highlight desaturation | Negative · Dye Saturation | ✅ v0.6 |
| Save / load custom stocks (My Stocks) | OFX: stock files (JSON) in a user folder | ⏳ OFX |

## Print
| Feature | MC Film | Status |
|---|---|---|
| 2383 / 2393 | Core | ✅ |
| Photo papers (Endura, Crystal Archive, ...) | Core | ✅ |
| Fuji Eterna CP | No measured data available | 🚫. We will not invent data under a real stock name. Our own *authored* print looks, clearly named as ours, are possible. |
| Printer lights / points | Core | ✅ |
| Print contrast | Core | ✅ |
| Bleach bypass (Authentic / Grunge, negative or print) | Core | ✅ |

## Optics and film texture
| Feature | MC Film | Status |
|---|---|---|
| Halation (gauge-dependent) | MC Film Halation | ✅ (DCTL sampling speckle on tiny lights; OFX gets a real blur) |
| Grain per dye layer, gauge-scaled | MC Film Grain | ✅ (animated by a keyframed Seed in DCTL, per frame in OFX) |
| Irradiation / film resolution / acutance | Planned: emulsion scatter (the near-white part of a highlight glow) and MTF-based softening per layer, gauge-scaled | ⏳ next after the Negative Designer |
| Pro Mist / diffusion | Planned | ⏳ |
| Chromatic aberration, vignette, Petzval | Planned | ⏳ |
| Gate weave & breath, dust & specks, film gate, perforations | Needs the frame number | ⏳ OFX |

## Colour tools (separate DCTLs)
| Feature | MC Film | Status |
|---|---|---|
| Hue / HSL | MC HSL Editor | ✅ |
| Skin tone | MC Skin Guard | ✅ |
| Balance (skin-driven WB / exposure, false colour in stops) | Planned; reuses the Skin Guard qualifier | ⏳ |
| Split tone / crossover | MC Pro Split: RGB offsets in five tonal zones, Blend, Pivot, Neutral Pivot, Clean Blacks / Whites, Sat Mask, Show Curves, Highlight Sat Mask, Show Ramp, ten transfer functions | ✅ v0.7 |
| Palette, Tone core, Curves | Planned | ⏳ |

## Product
| Feature | Plan |
|---|---|
| Licence key / activation | OFX |
| Code signing | Windows: Authenticode or Microsoft Trusted Signing. macOS: Developer ID + notarisation. Unsigned plugins are blocked by Windows Smart App Control and macOS Gatekeeper. |
| Installer | One installer for the OFX bundle, DCTLs and PowerGrades |
| Platforms | macOS (Metal) and Windows (CUDA, with an OpenCL fallback for AMD / Intel) |
