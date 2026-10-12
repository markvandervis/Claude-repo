"""Reference implementation of MC_Skin-Guard-v1.0.dctl.

MarkCaptures MC Skin Guard - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

A line-by-line Python mirror of the DCTL's colour maths, written so that the
maths can be inspected, tested and later ported to C++ (OFX) without Resolve.
Function names match the DCTL (Sg* prefix dropped, snake_case).  Everything is
plain float maths on (r, g, b) tuples; the frame-level function `process_frame`
mirrors the DCTL's transform() including the Evenness neighbourhood reads.

The DCTL runs in 32-bit float and this file in 64-bit, so results agree to
within float rounding, not bit for bit (the bit-exact properties - identity,
untouched greys - are tested on the compiled DCTL itself).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

ENC_DISPLAY, ENC_LOG, ENC_LINEAR, ENC_DWG, ENC_ACESCCT, ENC_CINEON = range(6)
ENCODINGS = (ENC_DISPLAY, ENC_LOG, ENC_LINEAR, ENC_DWG, ENC_ACESCCT, ENC_CINEON)
ENCODING_NAMES = {ENC_DISPLAY: "Display Rec.709 sRGB", ENC_LOG: "Log direct",
                  ENC_LINEAR: "Scene Linear", ENC_DWG: "DaVinci WG Intermediate",
                  ENC_ACESCCT: "ACES AP1 ACEScct", ENC_CINEON: "Cineon Log"}
SM_OFF, SM_MASK, SM_ISOLATE = range(3)

# --- constants (identical to the DCTL) ---------------------------------------
EPS = 1.0e-6
PULL_MAX = 0.9
PROTECT_SAT_MAX = 0.85
PROTECT_GAIN_MIN, PROTECT_GAIN_MAX = 0.25, 4.0
SKIN_SAT_RANGE = 0.5
EXPOSURE_STOPS = 1.0
DENSITY_STOPS = 1.0
NEUTRAL_START, NEUTRAL_WIDTH = 0.005, 0.03
DARK_CHROMA = 0.02
HUE_FEATHER_MIN, HUE_FEATHER_SOFT = 1.0, 12.0
SAT_FEATHER_MIN, SAT_FEATHER_SOFT = 0.15, 0.5
LUMA_FEATHER_MIN, LUMA_FEATHER_SOFT = 0.01, 0.10
FOLD_SAT_K, FOLD_LUMA_K, FOLD_LOG_TONE = 2.0, 0.3, 0.2
EVEN_REF_WIDTH = 1920.0
EVEN_RING_INNER, EVEN_RING_OUTER = 0.5, 1.0
EVEN_W_INNER, EVEN_W_OUTER = 0.7748, 0.3604
EVEN_SIGMA_C_DISPLAY, EVEN_SIGMA_L_DISPLAY = 0.08, 0.15
EVEN_SIGMA_C_LOG, EVEN_SIGMA_L_LOG = 0.04, 0.08
LUMA_W = (0.2126, 0.7152, 0.0722)
LOG_STOP = 0.07329248
SRGB_CUT, SRGB_SLOPE, SRGB_A, SRGB_B, SRGB_GAMMA = 0.0031308, 12.92, 1.055, 0.055, 1.0 / 2.4
DI_A, DI_B, DI_C, DI_M = 0.0075, 7.0, 0.07329248, 10.44426855
DI_LIN_CUT, DI_LOG_CUT = 0.00262409, 0.02740668
CCT_LOG_STOP = 1.0 / 17.52
CCT_CUT, CCT_TOE_A, CCT_TOE_B = 0.155251141552511, 0.0729055341958355, 10.5402377416545
CIN_WHITE, CIN_SCALE = 685.0 / 1023.0, 1023.0 / 300.0
CIN_BLACK_OFF, CIN_LOG_STOP = 0.0107977516, 0.0882785911
CIN_BLACK, CIN_TOE_SLOPE, LOG10_2 = 95.0 / 1023.0, 0.0857073970, 0.30102999566
CCT_LIN_CUT = 0.0078125

DWG_TO_REC709 = ((1.89871504, -0.79180471, -0.10691033),
                 (-0.16894835, 1.48839859, -0.31945024),
                 (-0.12152602, -0.31546761, 1.43699363))
AP1_TO_REC709 = ((1.70505099, -0.62179212, -0.08325887),
                 (-0.13025642, 1.14080474, -0.01054832),
                 (-0.02400336, -0.12896898, 1.15297233))
REC709_TO_DWG = ((0.56273797, 0.32348330, 0.11377874),
                 (0.07775428, 0.74978114, 0.17246458),
                 (0.06466018, 0.19195861, 0.74338121))
REC709_TO_AP1 = ((0.61309740, 0.33952315, 0.04737945),
                 (0.07019372, 0.91635388, 0.01345240),
                 (0.02061560, 0.10956978, 0.86981462))


@dataclass
class SkinGuardParams:
    """UI parameters, in slider units, with the DCTL's defaults."""
    amount: float = 100.0
    hue_centre: float = 27.0
    hue_width: float = 30.0
    sat_low: float = 10.0
    sat_high: float = 75.0
    luma_low: float = 0.0
    luma_high: float = 100.0
    softness: float = 50.0
    consolidate: float = 0.0
    redness: float = 0.0
    yellow_green: float = 0.0
    protect: float = 0.0
    protect_width: float = 40.0
    natural_sat: float = 35.0
    skin_sat: float = 0.0
    density: float = 0.0
    exposure: float = 0.0
    evenness: float = 0.0
    even_radius: float = 8.0
    bypass: int = 0
    encoding: int = ENC_DWG
    show_mask: int = SM_OFF

    _DCTL_NAMES = {
        "amount": "uiAmount", "hue_centre": "uiHueCentre", "hue_width": "uiHueWidth",
        "sat_low": "uiSatLow", "sat_high": "uiSatHigh", "luma_low": "uiLumaLow",
        "luma_high": "uiLumaHigh", "softness": "uiSoftness", "consolidate": "uiConsolidate",
        "redness": "uiRedness", "yellow_green": "uiYellowGreen", "protect": "uiProtect",
        "protect_width": "uiProtectWidth", "natural_sat": "uiNaturalSat",
        "skin_sat": "uiSkinSat", "density": "uiDensity", "exposure": "uiExposure",
        "evenness": "uiEvenness", "even_radius": "uiEvenRadius", "bypass": "uiBypass",
        "encoding": "uiEncoding", "show_mask": "uiShowMask",
    }

    def to_dctl_args(self):
        out = []
        for f in fields(self):
            value = getattr(self, f.name)
            name = self._DCTL_NAMES[f.name]
            out.append("%s=%s" % (name, int(value) if isinstance(value, int) else repr(float(value))))
        return out


# --- helpers ------------------------------------------------------------------
def saturate(x):
    return min(max(x, 0.0), 1.0)


def clamp(x, a, b):
    return min(max(x, a), b)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep01(x):
    t = saturate(x)
    return t * t * (3.0 - 2.0 * t)


def luma(c):
    return c[0] * LUMA_W[0] + c[1] * LUMA_W[1] + c[2] * LUMA_W[2]


def wrap_hue(h):
    w = math.fmod(h, 360.0)
    return w + 360.0 if w < 0.0 else w


def hue_delta(a, b):
    return math.fmod(a - b + 540.0, 360.0) - 180.0


# --- encodings ----------------------------------------------------------------
def di_encode(x):
    return (math.log2(x + DI_A) + DI_B) * DI_C if x > DI_LIN_CUT else x * DI_M


def di_decode(y):
    return 2.0 ** (min(y, 5.0) / DI_C - DI_B) - DI_A if y > DI_LOG_CUT else y / DI_M


def acescct_decode(y):
    return 2.0 ** (min(y, 4.0) * 17.52 - 9.72) if y > CCT_CUT else (y - CCT_TOE_A) / CCT_TOE_B


def acescct_encode(x):
    if x <= CCT_LIN_CUT:
        return CCT_TOE_B * x + CCT_TOE_A
    return (math.log2(x) + 9.72) / 17.52


def cineon_decode(y):
    if y < CIN_BLACK:
        return (y - CIN_BLACK) * CIN_TOE_SLOPE
    v = 10.0 ** (min(y - CIN_WHITE, 3.0) * CIN_SCALE)
    return (v - CIN_BLACK_OFF) / (1.0 - CIN_BLACK_OFF)


def cineon_encode(x):
    if x < 0.0:
        return CIN_BLACK + x / CIN_TOE_SLOPE
    v = x * (1.0 - CIN_BLACK_OFF) + CIN_BLACK_OFF
    return math.log2(v) * LOG10_2 / CIN_SCALE + CIN_WHITE


def srgb_encode(x):
    if x <= SRGB_CUT:
        return x * SRGB_SLOPE
    return SRGB_A * x ** SRGB_GAMMA - SRGB_B


def srgb_decode(y):
    if y <= SRGB_CUT * SRGB_SLOPE:
        return y / SRGB_SLOPE
    return ((y + SRGB_B) / SRGB_A) ** (1.0 / SRGB_GAMMA)


def log_stop(encoding):
    if encoding == ENC_ACESCCT:
        return CCT_LOG_STOP
    if encoding == ENC_CINEON:
        return CIN_LOG_STOP
    return LOG_STOP


def to_working(rgb, encoding):
    return tuple(di_encode(v) for v in rgb) if encoding == ENC_LINEAR else tuple(rgb)


def from_working(rgb, encoding):
    return tuple(di_decode(v) for v in rgb) if encoding == ENC_LINEAR else tuple(rgb)


def selects_elsewhere(encoding):
    return encoding not in (ENC_DISPLAY, ENC_LOG)


def _matrix(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def selection_rgb(w, encoding):
    if encoding == ENC_LINEAR:
        return tuple(srgb_encode(di_decode(v)) for v in w)
    if encoding == ENC_DWG:
        return tuple(srgb_encode(v) for v in _matrix(DWG_TO_REC709, [di_decode(v) for v in w]))
    if encoding == ENC_ACESCCT:
        return tuple(srgb_encode(v) for v in _matrix(AP1_TO_REC709, [acescct_decode(v) for v in w]))
    if encoding == ENC_CINEON:
        return tuple(srgb_encode(cineon_decode(v)) for v in w)
    return tuple(w)


def selection_to_working(s, encoding):
    lin = [srgb_decode(v) for v in s]
    if encoding == ENC_LINEAR:
        return tuple(di_encode(v) for v in lin)
    if encoding == ENC_DWG:
        return tuple(di_encode(v) for v in _matrix(REC709_TO_DWG, lin))
    if encoding == ENC_ACESCCT:
        return tuple(acescct_encode(v) for v in _matrix(REC709_TO_AP1, lin))
    if encoding == ENC_CINEON:
        return tuple(cineon_encode(v) for v in lin)
    return tuple(s)


# --- hue geometry -------------------------------------------------------------
def rgb_to_hue(c, mx, chroma):
    if chroma <= EPS:
        return 0.0
    if mx == c[0]:
        h = (c[1] - c[2]) / chroma
    elif mx == c[1]:
        h = 2.0 + (c[2] - c[0]) / chroma
    else:
        h = 4.0 + (c[0] - c[1]) / chroma
    return wrap_hue(h * 60.0)


def gamut_saturation(mx, chroma):
    return 0.0 if mx <= EPS else chroma / mx


def perceptual_saturation(mx, chroma):
    return 0.0 if mx <= EPS else min(chroma / mx, chroma / DARK_CHROMA)


def _hue_channel(n, hue, mx, chroma):
    k = math.fmod(n + hue / 60.0, 6.0)
    return mx - chroma * clamp(min(k, 4.0 - k), 0.0, 1.0)


def apply_hue(hue, mx, chroma):
    return (_hue_channel(5.0, hue, mx, chroma), _hue_channel(3.0, hue, mx, chroma),
            _hue_channel(1.0, hue, mx, chroma))


def measure(w, encoding):
    """(hue, perceptual saturation, luma) in the selection encoding."""
    s = selection_rgb(w, encoding)
    mx = max(s)
    chroma = mx - min(s)
    return (rgb_to_hue(s, mx, chroma), perceptual_saturation(mx, chroma), luma(s))


# --- qualifier ----------------------------------------------------------------
def hue_window(d, half_width, feather):
    return 1.0 - smoothstep01((abs(d) - half_width) / (2.0 * feather))


def sat_window(sat, lo, hi, feather):
    u = math.log(max(sat, 1.0e-4))
    u_lo = math.log(max(lo, 1.0e-4))
    u_hi = math.log(max(hi, 1.0e-4))
    rise = smoothstep01((u - (u_lo - 2.0 * feather)) / (2.0 * feather))
    fall = 1.0 - smoothstep01((u - u_hi) / (2.0 * feather))
    return rise * fall


def luma_window(l, lo, hi, feather):
    rise = smoothstep01((l - (lo - 2.0 * feather)) / (2.0 * feather))
    fall = 1.0 - smoothstep01((l - hi) / (2.0 * feather))
    return rise * fall


def neutral_guard(sat):
    return smoothstep01((sat - NEUTRAL_START) / NEUTRAL_WIDTH)


def fold_safe_sat_feather(feather, gain):
    return max(feather, FOLD_SAT_K * abs(gain - 1.0) / (1.0 + gain))


def fold_safe_luma_feather(feather, stops):
    return max(feather, FOLD_LUMA_K * abs(stops))


def tone_guard(l, stops, encoding):
    if encoding != ENC_LOG or stops == 0.0:
        return 1.0
    return smoothstep01(l / (FOLD_LOG_TONE * abs(stops)))


def sat_luma_mask(sat, l, sat_lo, sat_hi, sat_feather, luma_lo, luma_hi, luma_feather):
    return (neutral_guard(sat) * sat_window(sat, sat_lo, sat_hi, sat_feather) *
            luma_window(l, luma_lo, luma_hi, luma_feather))


# --- operators ----------------------------------------------------------------
def scale_chroma(c, gain):
    if gain == 1.0:
        return c
    y = luma(c)
    return tuple(y + (v - y) * gain for v in c)


def limit_chroma_gain(c, y, gain, limit_white):
    if gain <= 1.0:
        return gain
    g_max = 1.0e30
    mn = min(c)
    if y - mn > EPS and y > min(mn, 0.0):
        g_max = (y - min(mn, 0.0)) / (y - mn)
    mx = max(c)
    if limit_white and mx - y > EPS:
        g_max = min(g_max, (max(mx, 1.0) - y) / (mx - y))
    knee = max(1.0, 0.8 * g_max)
    if gain <= knee:
        return gain
    rng = max(g_max - knee, EPS)
    return knee + rng * (1.0 - math.exp(-(gain - knee) / rng))


def preserve_luminance(c, luma_before, encoding):
    luma_after = luma(c)
    if encoding == ENC_LOG:
        off = luma_before - luma_after
        return tuple(v + off for v in c)
    if luma_before <= EPS or luma_after <= EPS:
        return c
    mx = max(c)
    s = clamp(luma_before / luma_after, 0.25, 4.0)
    if mx > EPS:
        s = min(s, max(1.0, mx) / mx)
    return tuple(v * s for v in c)


def pull_hue(d, k_red, k_yellow, mask_sl, half_width, feather):
    k = k_red if d < 0.0 else k_yellow
    return d * (1.0 - k * mask_sl * hue_window(d, half_width, feather))


def apply_exposure(c, stops, encoding):
    if stops == 0.0:
        return c
    if encoding == ENC_LINEAR:
        gain = 2.0 ** stops
        return tuple(di_encode(di_decode(v) * gain) for v in c)
    if encoding != ENC_DISPLAY:
        off = stops * log_stop(encoding)
        return tuple(v + off for v in c)
    mx = max(c)
    if mx <= EPS:
        return c
    gain = 2.0 ** stops
    mx_new = mx * gain / (1.0 + mx * (gain - 1.0)) if mx < 1.0 else 1.0 + (mx - 1.0) * gain
    return tuple(v * (mx_new / mx) for v in c)


def step_limit(v, dv, lo, hi, k_want):
    if dv > EPS:
        return min(k_want, max((hi - v) / dv, 0.0))
    if dv < -EPS:
        return min(k_want, max((lo - v) / dv, 0.0))
    return k_want


def apply_evenness(c, mean_residual, k, encoding):
    if k <= 0.0:
        return c
    y = luma(c)
    r = [v - y for v in c]
    d = [m - rv for m, rv in zip(mean_residual, r)]
    if encoding == ENC_DISPLAY:
        lo, hi = min(0.0, min(c)), max(1.0, max(c))
        for v, dv in zip(c, d):
            k = step_limit(v, dv, lo, hi, k)
    return tuple(y + rv + k * dv for rv, dv in zip(r, d))


# --- pixel pipeline (mirrors SgSkinGuardPixel) --------------------------------
def skin_guard_pixel(w, meas, mask_l, sat_lo, sat_hi, sat_feather, hue_centre, half_width, hue_feather,
                     k_red, k_yellow, k_protect, protect_half, natural_sat, p_sat,
                     skin_sat_gain, exposure, density, even_k, mean_residual, encoding):
    sat = meas[1]
    mask_sl = neutral_guard(sat) * sat_window(sat, sat_lo, sat_hi, sat_feather) * mask_l
    d_in = hue_delta(meas[0], hue_centre)
    hue_win = hue_window(d_in, half_width, hue_feather)
    mask = mask_sl * hue_win
    mask_p = mask_sl * hue_window(d_in, protect_half, hue_feather)

    c = tuple(w)

    c = apply_evenness(c, mean_residual, even_k * mask, encoding)

    hue_ops = k_red > 0.0 or k_yellow > 0.0 or k_protect > 0.0

    if hue_ops or p_sat > 0.0 or skin_sat_gain != 1.0:
        cs = selection_rgb(c, encoding)
        cs0 = cs
        if hue_ops:
            mx = max(cs)
            chroma = mx - min(cs)
            hue_s = rgb_to_hue(cs, mx, chroma)
            d0 = hue_delta(hue_s, hue_centre)
            d1 = pull_hue(d0, k_red, k_yellow, mask_sl, half_width, hue_feather)
            d2 = pull_hue(d1, k_protect, k_protect, mask_sl, protect_half, hue_feather)
            d_sel = d2 - d0
            if d_sel != 0.0 and chroma > EPS:
                luma_before = luma(cs)
                cs = apply_hue(wrap_hue(hue_s + d_sel), mx, chroma)
                cs = preserve_luminance(cs, luma_before, encoding)
        if p_sat > 0.0:
            g = (natural_sat / max(sat, 1.0e-3)) ** p_sat
            g = 1.0 + mask_p * (clamp(g, PROTECT_GAIN_MIN, PROTECT_GAIN_MAX) - 1.0)
            cs = scale_chroma(cs, limit_chroma_gain(cs, luma(cs), g, encoding == ENC_DISPLAY))
        if skin_sat_gain != 1.0:
            mx = max(cs)
            s_now = perceptual_saturation(mx, mx - min(cs))
            m = neutral_guard(s_now) * sat_window(s_now, sat_lo, sat_hi, sat_feather) * mask_l * hue_win
            g = 1.0 + m * (skin_sat_gain - 1.0)
            cs = scale_chroma(cs, limit_chroma_gain(cs, luma(cs), g, encoding == ENC_DISPLAY))
        if cs != cs0:
            c = selection_to_working(cs, encoding)

    stops = (mask * (exposure - density * saturate(sat)) *
             tone_guard(meas[2], abs(exposure) + abs(density), encoding))
    return apply_exposure(c, stops, encoding)


def apply_preview(rgb, mask, mode, encoding):
    if mode == SM_MASK:
        return (mask, mask, mask)
    g = luma(rgb)
    dull = (g * 0.5,) * 3 if encoding == ENC_DISPLAY else (g,) * 3
    t = saturate(mask)
    return tuple(lerp(a, b, t) for a, b in zip(dull, rgb))


# --- frame level (mirrors the DCTL's image access and transform) -------------
class _Derived:
    """UI -> pipeline arguments, exactly as transform() computes them."""

    def __init__(self, p: SkinGuardParams):
        k = 0.01
        self.amount = saturate(p.amount * k)
        self.activity = (p.consolidate + abs(p.redness) + abs(p.yellow_green) + p.protect +
                         abs(p.skin_sat) + abs(p.density) + abs(p.exposure) + p.evenness)
        self.half_width = 0.5 * p.hue_width
        self.protect_half = self.half_width + 0.5 * p.protect_width
        self.hue_feather = HUE_FEATHER_MIN + HUE_FEATHER_SOFT * p.softness * k
        self.sat_lo = p.sat_low * k
        self.sat_hi = max(p.sat_high * k, self.sat_lo)
        self.luma_lo = p.luma_low * k
        self.luma_hi = max(p.luma_high * k, self.luma_lo)
        self.k_red = PULL_MAX * saturate((p.consolidate + p.redness) * k)
        self.k_yellow = PULL_MAX * saturate((p.consolidate + p.yellow_green) * k)
        self.k_protect = PULL_MAX * saturate(p.protect * k)
        self.p_sat = PROTECT_SAT_MAX * saturate(p.protect * k)
        self.natural_sat = clamp(p.natural_sat * k, self.sat_lo, self.sat_hi)
        self.skin_sat = 1.0 + SKIN_SAT_RANGE * p.skin_sat * k
        self.exposure = EXPOSURE_STOPS * p.exposure * k
        self.density = DENSITY_STOPS * p.density * k
        self.even_k = saturate(p.evenness * k)
        self.sat_feather = fold_safe_sat_feather(SAT_FEATHER_MIN + SAT_FEATHER_SOFT * p.softness * k,
                                                 self.skin_sat)
        self.luma_feather = fold_safe_luma_feather(LUMA_FEATHER_MIN + LUMA_FEATHER_SOFT * p.softness * k,
                                                   abs(self.exposure) + abs(self.density))


def skin_mask(rgb, p: SkinGuardParams):
    """The skin mask the DCTL applies (and shows with Show Skin Mask = Mask)."""
    d = _Derived(p)
    w = to_working(rgb, p.encoding)
    meas = measure(w, p.encoding)
    m_sl = sat_luma_mask(meas[1], meas[2], d.sat_lo, d.sat_hi, d.sat_feather,
                         d.luma_lo, d.luma_hi, d.luma_feather)
    return m_sl * hue_window(hue_delta(meas[0], p.hue_centre), d.half_width, d.hue_feather)


def gather_evenness(frame, width, height, x, y, centre, radius, encoding):
    sigma_c = EVEN_SIGMA_C_DISPLAY if encoding == ENC_DISPLAY else EVEN_SIGMA_C_LOG
    sigma_l = EVEN_SIGMA_L_DISPLAY if encoding == ENC_DISPLAY else EVEN_SIGMA_L_LOG
    inv_c2, inv_l2 = 1.0 / (sigma_c * sigma_c), 1.0 / (sigma_l * sigma_l)
    luma_c = luma(centre)
    res_c = tuple(v - luma_c for v in centre)
    sum_w = 1.0
    sum_r = list(res_c)
    for ring in (0, 1):
        rad = radius * (EVEN_RING_INNER if ring == 0 else EVEN_RING_OUTER)
        spatial = EVEN_W_INNER if ring == 0 else EVEN_W_OUTER
        for i in range(8):
            a = (i * 45.0 + ring * 22.5) * (3.14159265 / 180.0)
            dx = int(math.floor(math.cos(a) * rad + 0.5))
            dy = int(math.floor(math.sin(a) * rad + 0.5))
            xc = min(max(x + dx, 0), width - 1)
            yc = min(max(y + dy, 0), height - 1)
            n = to_working(frame[yc * width + xc], encoding)
            yn = luma(n)
            dist = sum(((nv - yn) - rv) ** 2 for nv, rv in zip(n, res_c))
            wt = spatial * math.exp(-dist * inv_c2 - (yn - luma_c) ** 2 * inv_l2)
            sum_w += wt
            for j in range(3):
                sum_r[j] += wt * (n[j] - yn)
    return tuple(v / sum_w for v in sum_r)


def process_frame(frame, width, height, p: SkinGuardParams):
    """Process a row-major list of (r, g, b) pixels, like the DCTL in Resolve."""
    d = _Derived(p)
    out = []
    preview_on = p.show_mask != SM_OFF
    for y in range(height):
        for x in range(width):
            rgb_in = tuple(frame[y * width + x])
            if p.bypass:
                out.append(rgb_in)
                continue
            if not preview_on and (d.amount <= 0.0 or d.activity <= 0.0):
                out.append(rgb_in)
                continue
            w = to_working(rgb_in, p.encoding)
            meas = measure(w, p.encoding)
            m_l = luma_window(meas[2], d.luma_lo, d.luma_hi, d.luma_feather)
            m_sl = neutral_guard(meas[1]) * sat_window(meas[1], d.sat_lo, d.sat_hi, d.sat_feather) * m_l
            d_in = hue_delta(meas[0], p.hue_centre)
            mask = m_sl * hue_window(d_in, d.half_width, d.hue_feather)
            mask_p = m_sl * hue_window(d_in, d.protect_half, d.hue_feather) if d.k_protect > 0.0 else 0.0

            out_rgb = rgb_in
            if d.amount > 0.0 and d.activity > 0.0 and (mask > 0.0 or mask_p > 0.0):
                mean_res = (0.0, 0.0, 0.0)
                if d.even_k > 0.0 and mask > 0.0:
                    radius = max(p.even_radius * width / EVEN_REF_WIDTH, 1.0)
                    mean_res = gather_evenness(frame, width, height, x, y, w, radius, p.encoding)
                out_w = skin_guard_pixel(w, meas, m_l, d.sat_lo, d.sat_hi, d.sat_feather, p.hue_centre, d.half_width, d.hue_feather,
                                         d.k_red, d.k_yellow, d.k_protect, d.protect_half,
                                         d.natural_sat, d.p_sat, d.skin_sat, d.exposure, d.density,
                                         d.even_k, mean_res, p.encoding)
                if out_w != tuple(w):
                    out_rgb = from_working(out_w, p.encoding)
                    if d.amount < 1.0:
                        out_rgb = tuple(lerp(a, b, d.amount) for a, b in zip(rgb_in, out_rgb))
            if preview_on:
                out_rgb = apply_preview(out_rgb, mask, p.show_mask, p.encoding)
            out.append(tuple(out_rgb))
    return out


def process_pixel(rgb, p: SkinGuardParams):
    """Single pixel (Evenness sees a 1x1 frame, i.e. only the pixel itself)."""
    return process_frame([tuple(rgb)], 1, 1, p)[0]
