"""Reference implementation of Lightroom_Color_Mixer.dctl.

This is a readable, dependency-free port of the DCTL's pixel maths.  It exists
for three reasons:

* it documents the algorithm in a form that can be read and stepped through
  without a GPU,
* it lets the test suite cross-check the compiled DCTL against an independent
  implementation of the same maths, and
* it is used to render the example / test images in ``tests/images``.

It follows the DCTL line for line, including the neutral-value early-outs, so
that the two stay comparable.  The only intentional difference is arithmetic
precision: the DCTL runs in 32-bit float on the GPU, this runs in Python's
64-bit floats, so results agree to roughly 1e-6 rather than bit exactly.

Colour-space assumptions are documented in README.md and in the DCTL header.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields

# --------------------------------------------------------------------------
# Constants (mirrors of the #defines in the DCTL)
# --------------------------------------------------------------------------
EPS = 1.0e-6
HUE_MAX_DEG = 30.0
LOG_STOP = 0.07329248
DISPLAY_STOPS = 1.5
DARK_CHROMA = 0.02
VIB_SKIN = 0.40
SKIN_CENTRE_DEG = 32.0
SKIN_WIDTH_DEG = 45.0

LUMA_R, LUMA_G, LUMA_B = 0.2126, 0.7152, 0.0722

DI_A, DI_B, DI_C, DI_M = 0.0075, 7.0, 0.07329248, 10.44426855
DI_LIN_CUT, DI_LOG_CUT = 0.00262409, 0.02740668

ENC_DISPLAY, ENC_LOG, ENC_LINEAR = 0, 1, 2
PV_OFF, PV_MASK, PV_ISOLATE = 0, 1, 2

#: Region centres in degrees, in the order the UI presents them.
REGION_NAMES = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")
REGION_CENTRES = (0.0, 30.0, 60.0, 120.0, 180.0, 240.0, 285.0, 330.0)

#: Arc boundaries used by the partition of unity: centre[i] .. centre[i+1],
#: with the last arc wrapping through 360 back to red.
_ARCS = ((0.0, 30.0), (30.0, 60.0), (60.0, 120.0), (120.0, 180.0),
         (180.0, 240.0), (240.0, 285.0), (285.0, 330.0), (330.0, 360.0))


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
@dataclass
class MixerParams:
    """All UI controls, in slider units (the same numbers Resolve shows)."""

    encoding: int = ENC_DISPLAY

    global_saturation: float = 0.0      # -100 .. +100
    vibrance: float = 0.0               # -100 .. +100
    amount: float = 100.0               # 0 .. 100

    hue: list = field(default_factory=lambda: [0.0] * 8)   # -100 .. +100 per region
    saturation: list = field(default_factory=lambda: [0.0] * 8)
    luminance: list = field(default_factory=lambda: [0.0] * 8)

    protect_neutrals: float = 35.0      # 0 .. 100
    preserve_luminance: float = 75.0    # 0 .. 100
    hue_falloff: float = 50.0           # 0 .. 100
    saturation_protection: float = 50.0  # 0 .. 100

    preview: int = PV_OFF
    preview_region: int = 0
    bypass: bool = False

    # -- convenience ------------------------------------------------------
    def set_region(self, name: str, hue=None, sat=None, lum=None) -> "MixerParams":
        i = REGION_NAMES.index(name)
        if hue is not None:
            self.hue[i] = hue
        if sat is not None:
            self.saturation[i] = sat
        if lum is not None:
            self.luminance[i] = lum
        return self

    def to_dctl_args(self) -> list:
        """The equivalent ``name=value`` arguments for tests/dctl_harness."""
        pretty = ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")
        args = [
            f"uiEncoding={self.encoding}",
            f"uiGlobalSat={self.global_saturation!r}",
            f"uiVibrance={self.vibrance!r}",
            f"uiAmount={self.amount!r}",
            f"uiProtectNeutrals={self.protect_neutrals!r}",
            f"uiPreserveLum={self.preserve_luminance!r}",
            f"uiHueFalloff={self.hue_falloff!r}",
            f"uiSatProtect={self.saturation_protection!r}",
            f"uiPreview={self.preview}",
            f"uiPreviewRegion={self.preview_region}",
            f"uiBypass={int(self.bypass)}",
        ]
        for i, name in enumerate(pretty):
            args.append(f"ui{name}Hue={self.hue[i]!r}")
            args.append(f"ui{name}Sat={self.saturation[i]!r}")
            args.append(f"ui{name}Lum={self.luminance[i]!r}")
        return args


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def saturate(x):
    return clamp(x, 0.0, 1.0)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep01(x):
    t = saturate(x)
    return t * t * (3.0 - 2.0 * t)


def luma(rgb):
    return rgb[0] * LUMA_R + rgb[1] * LUMA_G + rgb[2] * LUMA_B


def scale3(rgb, s):
    return (rgb[0] * s, rgb[1] * s, rgb[2] * s)


def offset3(rgb, s):
    return (rgb[0] + s, rgb[1] + s, rgb[2] + s)


def lerp3(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def wrap_hue(h):
    w = math.fmod(h, 360.0)
    return w + 360.0 if w < 0.0 else w


def hue_delta(a, b):
    return math.fmod(a - b + 540.0, 360.0) - 180.0


# --------------------------------------------------------------------------
# Working space
# --------------------------------------------------------------------------
def di_encode(x):
    """Scene linear -> DaVinci Intermediate."""
    if x > DI_LIN_CUT:
        return (math.log2(x + DI_A) + DI_B) * DI_C
    return x * DI_M


def di_decode(y):
    if y > DI_LOG_CUT:
        # the exponent is limited so that an absurd working value cannot decode
        # to infinity; a DI code value of 5 is already 2**61 in linear
        return 2.0 ** (min(y, 5.0) / DI_C - DI_B) - DI_A
    return y / DI_M


def rgb_to_working_space(rgb, encoding):
    if encoding == ENC_LINEAR:
        return (di_encode(rgb[0]), di_encode(rgb[1]), di_encode(rgb[2]))
    return rgb


def working_space_to_rgb(rgb, encoding):
    if encoding == ENC_LINEAR:
        return (di_decode(rgb[0]), di_decode(rgb[1]), di_decode(rgb[2]))
    return rgb


# --------------------------------------------------------------------------
# Hue geometry
# --------------------------------------------------------------------------
def rgb_to_hue(rgb, mx, chroma):
    """HSV hue angle in degrees; 0 for neutral pixels, where hue is undefined."""
    if chroma <= EPS:
        return 0.0
    r, g, b = rgb
    if mx == r:
        h = (g - b) / chroma
    elif mx == g:
        h = 2.0 + (b - r) / chroma
    else:
        h = 4.0 + (r - g) / chroma
    return wrap_hue(h * 60.0)


def gamut_saturation(mx, chroma):
    """HSV saturation.  Above 1 means a channel has gone negative."""
    if mx <= EPS:
        return 0.0
    return chroma / mx


def perceptual_saturation(mx, chroma):
    """HSV saturation, damped for very dark pixels where the reading is noise."""
    if mx <= EPS:
        return 0.0
    return min(chroma / mx, chroma / DARK_CHROMA)


#: Backwards-compatible alias used by the test suite for readability.
saturation_measure = perceptual_saturation


def _hue_channel(n, hue_deg, mx, chroma):
    k = math.fmod(n + hue_deg / 60.0, 6.0)
    return mx - chroma * clamp(min(k, 4.0 - k), 0.0, 1.0)


def apply_hue(hue_deg, mx, chroma):
    """Rebuild RGB at a new hue angle, holding HSV value and saturation."""
    return (_hue_channel(5.0, hue_deg, mx, chroma),
            _hue_channel(3.0, hue_deg, mx, chroma),
            _hue_channel(1.0, hue_deg, mx, chroma))


# --------------------------------------------------------------------------
# Region weighting
# --------------------------------------------------------------------------
def blend_shape(t, falloff):
    """Shaped cross-fade: 0 at t=0, 1 at t=1, 0.5 at t=0.5 for any falloff."""
    p = 1.0 + (1.0 - saturate(falloff)) * 4.0
    tc = saturate(t)
    a = tc ** p
    b = (1.0 - tc) ** p
    return a / max(a + b, EPS)


def find_hue_band(hue_deg, falloff):
    """Return (segment, next segment, cross-fade position) for a hue angle."""
    seg = 7
    for i, (lo, hi) in enumerate(_ARCS):
        if hue_deg < hi:
            seg = i
            break
    lo, hi = _ARCS[seg]
    return seg, (seg + 1) & 7, blend_shape((hue_deg - lo) / (hi - lo), falloff)


def hue_weight(region, seg, seg_next, blend):
    w = 0.0
    if region == seg:
        w += 1.0 - blend
    if region == seg_next:
        w += blend
    return w


def region_weights(hue_deg, falloff):
    """All eight region weights.  They sum to exactly 1 for every hue."""
    seg, seg_next, blend = find_hue_band(hue_deg, falloff)
    return [hue_weight(i, seg, seg_next, blend) for i in range(8)]


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------
def scale_chroma(rgb, gain):
    """Scale chroma about the pixel's own luma: exactly luma preserving."""
    if gain == 1.0:
        return rgb
    y = luma(rgb)
    return (y + (rgb[0] - y) * gain,
            y + (rgb[1] - y) * gain,
            y + (rgb[2] - y) * gain)


def apply_saturation(amount):
    return 1.0 + amount


def apply_global_saturation(amount):
    return 1.0 + amount


def protect_neutrals(sat, protect):
    threshold = 0.05 + 0.45 * saturate(protect)
    return smoothstep01(sat / threshold)


def skin_proximity(hue_deg):
    d = abs(hue_delta(hue_deg, SKIN_CENTRE_DEG))
    return 1.0 - smoothstep01(d / SKIN_WIDTH_DEG)


def apply_vibrance(amount, sat, hue_deg):
    if amount == 0.0:
        return 1.0
    s = saturate(sat)
    skin = 1.0 - VIB_SKIN * skin_proximity(hue_deg)
    w = (1.0 - s) ** 1.5 if amount > 0.0 else (0.35 + 0.65 * (1.0 - s))
    return 1.0 + amount * w * skin


def preserve_luminance(rgb, luma_before, strength, encoding):
    if strength <= 0.0:
        return rgb
    luma_after = luma(rgb)
    if encoding != ENC_DISPLAY:
        return offset3(rgb, (luma_before - luma_after) * strength)
    if luma_before <= EPS or luma_after <= EPS:
        return rgb
    s = clamp(luma_before / luma_after, 0.25, 4.0)
    return scale3(rgb, 1.0 + (s - 1.0) * strength)


def apply_luminance(rgb, amount, encoding):
    """Region luminance.

    Log:     a code-value offset, i.e. an exposure change.
    Linear:  decode, scale, re-encode - an exact exposure change.
    Display: a Moebius tone response that fixes both 0 and 1, applied to the
             pixel's value and passed on as a common scale factor so hue and
             HSV saturation survive untouched.  Its slope is bounded everywhere,
             unlike the 1-(1-x)**g family, which is vertical at white.  Above
             display white the curve has a pole, so it is continued there by a
             plain gain.
    """
    if amount == 0.0:
        return rgb
    if encoding == ENC_LOG:
        return offset3(rgb, amount * LOG_STOP)
    if encoding == ENC_LINEAR:
        gain = 2.0 ** amount
        return tuple(di_encode(di_decode(v) * gain) for v in rgb)

    mx = max(rgb)
    if mx <= EPS:
        return rgb
    gain = 2.0 ** (amount * DISPLAY_STOPS)
    if mx < 1.0:
        mx_new = mx * gain / (1.0 + mx * (gain - 1.0))
    else:
        mx_new = 1.0 + (mx - 1.0) * gain
    return scale3(rgb, mx_new / mx)


def protect_saturation(rgb, sat_before, protect):
    """Soft, one-sided gamut compressor.

    Only saturation increases are limited, and the compressed result approaches
    the ceiling without reaching it, so at protect = 1 an in-gamut pixel can
    never be pushed past saturation 1 - the point where a channel goes negative.
    The chroma gain is solved for exactly rather than approximated, which is
    what makes the operator continuous at the knee.
    """
    mx, mn = max(rgb), min(rgb)
    chroma = mx - mn
    sat_now = gamut_saturation(mx, chroma)
    if sat_now <= sat_before:
        return rgb

    ceiling = max(sat_before, 2.0 - saturate(protect))
    knee = max(sat_before, ceiling * 0.65)
    if sat_now <= knee:
        return rgb

    rng = max(ceiling - knee, EPS)
    target = knee + rng * (1.0 - math.exp(-(sat_now - knee) / rng))

    y = luma(rgb)
    denom = chroma - target * (mx - y)
    gain = (target * y / denom) if (y > EPS and denom > EPS) else (target / max(sat_now, EPS))
    return scale_chroma(rgb, clamp(gain, 0.0, 1.0))


# --------------------------------------------------------------------------
# Pixel pipeline
# --------------------------------------------------------------------------
def apply_color_mixer_core(w, hue_deg, d_hue, d_sat, d_lum, global_sat, vibrance,
                           protect_neutrals_amt, preserve_lum, sat_protect, encoding):
    c = w
    mx, mn = max(c), min(c)
    sat = perceptual_saturation(mx, mx - mn)
    sat_in = gamut_saturation(mx, mx - mn)

    k_global = apply_global_saturation(global_sat) * apply_vibrance(vibrance, sat, hue_deg)
    if k_global != 1.0:
        c = scale_chroma(c, k_global)
        mx, mn = max(c), min(c)

    mask = protect_neutrals(sat, protect_neutrals_amt)
    hue_amt, sat_amt, lum_amt = d_hue * mask, d_sat * mask, d_lum * mask

    if hue_amt != 0.0:
        luma_before = luma(c)
        c = apply_hue(wrap_hue(hue_deg + hue_amt * HUE_MAX_DEG), mx, mx - mn)
        c = preserve_luminance(c, luma_before, preserve_lum, encoding)

    if sat_amt != 0.0:
        c = scale_chroma(c, apply_saturation(sat_amt))

    if lum_amt != 0.0:
        c = apply_luminance(c, lum_amt, encoding)

    return protect_saturation(c, sat_in, sat_protect)


def apply_preview(rgb, weight, mode, encoding):
    if mode == PV_MASK:
        return (weight, weight, weight)
    g = luma(rgb)
    dull = (g, g, g)
    if encoding == ENC_DISPLAY:
        dull = scale3(dull, 0.5)
    return lerp3(dull, rgb, saturate(weight))


def process_pixel(rgb, p: MixerParams):
    """Full per-pixel transform; mirrors ``transform()`` in the DCTL."""
    if p.bypass:
        return rgb

    k = 0.01
    amount = saturate(p.amount * k)

    activity = abs(p.global_saturation) + abs(p.vibrance)
    for i in range(8):
        activity += abs(p.hue[i]) + abs(p.saturation[i]) + abs(p.luminance[i])

    preview_on = p.preview != PV_OFF
    if not preview_on and (amount <= 0.0 or activity <= 0.0):
        return rgb

    w = rgb_to_working_space(rgb, p.encoding)

    mx, mn = max(w), min(w)
    hue_deg = rgb_to_hue(w, mx, mx - mn)

    seg, seg_next, blend = find_hue_band(hue_deg, p.hue_falloff * k)
    weights = [hue_weight(i, seg, seg_next, blend) for i in range(8)]

    d_hue = sum(weights[i] * p.hue[i] for i in range(8)) * k
    d_sat = sum(weights[i] * p.saturation[i] for i in range(8)) * k
    d_lum = sum(weights[i] * p.luminance[i] for i in range(8)) * k

    out_w = apply_color_mixer_core(
        w, hue_deg, d_hue, d_sat, d_lum,
        p.global_saturation * k, p.vibrance * k,
        p.protect_neutrals * k, p.preserve_luminance * k,
        p.saturation_protection * k, p.encoding)

    out = working_space_to_rgb(out_w, p.encoding)

    if amount < 1.0:
        out = lerp3(rgb, out, amount)

    if preview_on:
        out = apply_preview(out, hue_weight(p.preview_region, seg, seg_next, blend),
                            p.preview, p.encoding)
    return out


def process_image(pixels, p: MixerParams):
    """Apply the mixer to a flat sequence of (r, g, b) tuples."""
    return [process_pixel(px, p) for px in pixels]


__all__ = [name for name in dir() if not name.startswith("_")]
