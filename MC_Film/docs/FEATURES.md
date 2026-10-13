# MC Film: feature map

The functionality a professional film-emulation suite needs, using the current commercial plugins (EMBR among them) as a functional reference: what exists, not how it's built. For each feature this lists where it lives in MC Film and its status. "OFX" means it needs the plugin, because it needs file access, the frame number, multi-pass rendering or a custom UI.

Status: ✅ done · 🟡 partly / approximation · ⏳ planned · 🚫 not possible honestly

## Input / output
| Feature | MC Film | Status |
|---|---|---|
| Input colour space (DWG, ACEScct, linear, Rec709) | Core · Input Encoding | ✅ |
| Output Rec709 2.4 / 2.2, sRGB, P3 2.6, Rec2020 | Core · Output | ✅ (2.2 added in v0.4) |
| Output Cineon (negative out) | Core · Output Negative Cineon Log | ✅ |
| Output DWG | Core · Output DaVinci WG Intermediate | ✅ |
| White point D65 / D60 / D55 | Core · White Point | ✅ v0.4 |
| Presets / Looks | OFX preset browser; meanwhile Resolve PowerGrades | ⏳ OFX |
| Export LUT (.cube) | Offline export tool from the reference model, then in OFX. Exported LUTs carry the CC BY-SA stock-data notice. | ⏳ |

## Negative
| Feature | MC Film | Status |
|---|---|---|
| Film stock library | Core · 13 negatives from measured data | ✅ |
| Film format 8mm / Super 8 / 16 / Super 16 / 35 / 65 | Grain + Halation · Gauge | ✅ (8mm regular to add) |
| Film speed / Auto (stock) | Grain uses each stock's granularity, which is "Auto". A manual speed override goes into Grain. | 🟡 |
| Strength (mix) | OFX global mix. In DCTL, use node Key Output gain. | ⏳ |
| Exposure, Push / Pull | Core | ✅ |
| Scene Temp / Tint | Core v0.4 | ✅ |
| Negative saturation | Core · Film Saturation | ✅ |
| Rendering Natural / Vivid | Film Saturation covers it; a "Vivid" preset value in OFX | 🟡 |
| Contrast / contrast presets | Core · Negative Contrast; presets in OFX | 🟡 |
| Layer gammas / dye crossover | Core v0.4 · Red / Green / Blue Layer Contrast | ✅ |
| Open / Close, Shadow & Highlight roll, Black / White anchor, Highlight latitude, Black depth, Base fog | **Negative Designer**: reshaping the stock's curves (toe, shoulder, latitude, fog) | ⏳ next |
| Dye saturation (per dye) | Negative Designer: dye density scaling | ⏳ next |
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
| Irradiation / film resolution / acutance | Planned: an MTF-based softening per layer, gauge-scaled | ⏳ |
| Pro Mist / diffusion | Planned | ⏳ |
| Chromatic aberration, vignette, Petzval | Planned | ⏳ |
| Gate weave & breath, dust & specks, film gate, perforations | Needs the frame number | ⏳ OFX |

## Colour tools (separate DCTLs)
| Feature | MC Film | Status |
|---|---|---|
| Hue / HSL | MC HSL Editor | ✅ |
| Skin tone | MC Skin Guard | ✅ |
| Balance (skin-driven WB / exposure, false colour in stops) | Planned; reuses the Skin Guard qualifier | ⏳ |
| Cast & crossover, Palette, Tone core, Curves | Planned | ⏳ |

## Product
| Feature | Plan |
|---|---|
| Licence key / activation | OFX |
| Code signing | Windows: Authenticode or Microsoft Trusted Signing. macOS: Developer ID + notarisation. Unsigned plugins are blocked by Windows Smart App Control and macOS Gatekeeper. |
| Installer | One installer for the OFX bundle, DCTLs and PowerGrades |
| Platforms | macOS (Metal) and Windows (CUDA, with an OpenCL fallback for AMD / Intel) |
