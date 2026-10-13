"""MC Pro Split - RGB split tone in five tonal zones: reference implementation.

MarkCaptures MC Pro Split - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Mirrors src/MC_Pro-Split.dctl.in.  Works directly on the log code values y
of the chosen Transfer Function (in whatever gamut the image is in), where
adding to a channel is an exposure shift of that channel.  Scene Linear is
worked on as DaVinci Intermediate.

    stop = TF(0.36) - TF(0.18)                      code values per stop
    x    = (luma(y) - TF(0.18 x 2^pivot)) / stop    brightness in stops
    Five zones, Lo / Lo-Mid / Mid / Hi-Mid / Hi, centred at -4, -2, 0, +2, +4
    stops.  Between two neighbouring centres the zone offsets blend with a
    smoothstep, outside the ends the end zone holds, so the weights always sum
    to 1 (the same setting on all five zones is a plain offset):
        o(x) = (1 - f) Z_i + f Z_i+1
    y' = y + SCALE x Blend x o(x) x clean(x) x satmask

    Neutral Pivot  removes the tint (zero-sum part) of the Mid zone, so the
                   pivot grey only gets lighter or darker, never coloured
    Clean Blacks   fades the toning out towards black
    Clean Whites   fades it out towards the brightest highlights
    Sat Mask       fades it out on saturated colours (tones the neutrals)

The weights change by at most 0.75 per stop, and SCALE keeps the offset's
change per stop below the change of the brightness itself, so a grey ramp
can never reverse.
"""

import math

import numpy as np

STOP = 0.07329248             # DaVinci Intermediate log per stop (above the toe)
MIDGRAY = 0.18
SCALE = 0.464                 # offset in stops at a zone slider of 100 (about half a stop)
ZONES = ("Lo", "Lo-Mid", "Mid", "Hi-Mid", "Hi")
ZONE_CENTRE0, ZONE_STEP = -4.0, 2.0
# Clean Blacks fades from the transfer function's black (TF(0)) up over
# BLACK_WIDTH stops, but never above BLACK_TOP stops (for curves whose black
# sits close to grey on the log scale); Clean Whites from WHITE_START stops.
BLACK_WIDTH = 2.5
BLACK_TOP = -1.0
WHITE_START, WHITE_WIDTH = 2.5, 2.5
SAT_CHROMA = 0.08             # chroma (log) at which Sat Mask is fully on
LUMA = (0.30, 0.60, 0.10)

DWG_TO_REC709 = np.array([[1.89871504, -0.79180471, -0.10691033],
                          [-0.16894835, 1.48839859, -0.31945024],
                          [-0.12152602, -0.31546761, 1.43699363]])
REC709_TO_DWG = np.linalg.inv(DWG_TO_REC709)
AP1_TO_REC709 = np.array([[1.70505099, -0.62179212, -0.08325887],
                          [-0.13025642, 1.14080474, -0.01054832],
                          [-0.02400336, -0.12896898, 1.15297233]])
AP1_TO_DWG = REC709_TO_DWG @ AP1_TO_REC709
DWG_TO_AP1 = np.linalg.inv(AP1_TO_DWG)

ENCODINGS = [("TF_DI", "DaVinci Intermediate"), ("TF_ACESCCT", "ACEScct"), ("TF_LOGC3", "ARRI LogC3"),
             ("TF_LOGC4", "ARRI LogC4"), ("TF_SLOG3", "Sony S-Log3"), ("TF_VLOG", "Panasonic V-Log"),
             ("TF_CLOG3", "Canon Log 3"), ("TF_LOG3G10", "RED Log3G10"), ("TF_CINEON", "Cineon Log"),
             ("TF_LINEAR", "Scene Linear")]

DEFAULTS = dict(zones=np.zeros((5, 3)), blend=100.0, pivot=0.0, neutral=0.0, clean_blacks=30.0,
                clean_whites=30.0, sat_mask=0.0)

_C4A = (2.0 ** 18 - 16.0) / 117.45
_C4B = (1023.0 - 95.0) / 1023.0
_C4C = 95.0 / 1023.0
_C4S = (7.0 * math.log(2.0) * 2.0 ** (7.0 - 14.0 * _C4C / _C4B)) / (_C4A * _C4B)
_C4T = (2.0 ** (14.0 * (-_C4C / _C4B) + 6.0) - 64.0) / _C4A
_CIN_BLACK = 10.0 ** ((95.0 - 685.0) / 300.0)


def tf_encode(x, tf):
    """Scene linear -> code value of the transfer function (the published curves)."""
    if tf in ("TF_DI", "TF_LINEAR"):
        return di_encode(x)
    if tf == "TF_ACESCCT":
        return cct_encode(max(x, 1e-10)) if x > 0.0078125 else 10.5402377416545 * x + 0.0729055341958355
    if tf == "TF_LOGC3":
        return 0.247190 * math.log10(5.555556 * x + 0.052272) + 0.385537 if x > 0.010591 else 5.367655 * x + 0.092809
    if tf == "TF_LOGC4":
        return (math.log2(_C4A * x + 64.0) - 6.0) / 14.0 * _C4B + _C4C if x >= _C4T else (x - _C4T) / _C4S
    if tf == "TF_SLOG3":
        if x >= 0.01125000:
            return (420.0 + math.log10((x + 0.01) / 0.19) * 261.5) / 1023.0
        return (x * (171.2102946929 - 95.0) / 0.01125 + 95.0) / 1023.0
    if tf == "TF_VLOG":
        return 5.6 * x + 0.125 if x < 0.01 else 0.241514 * math.log10(x + 0.00873) + 0.598206
    if tf == "TF_CLOG3":
        if x < -0.014:
            return -0.36726845 * math.log10(-x * 14.98325 + 1.0) + 0.12783901
        if x <= 0.014:
            return 1.9754798 * x + 0.12512219
        return 0.36726845 * math.log10(x * 14.98325 + 1.0) + 0.12240537
    if tf == "TF_LOG3G10":
        x = x + 0.01
        return x * 15.1927 if x < 0.0 else 0.224282 * math.log10(x * 155.975327 + 1.0)
    if tf == "TF_CINEON":
        return (685.0 + 300.0 * math.log10(max(x * (1.0 - _CIN_BLACK) + _CIN_BLACK, 1e-10))) / 1023.0
    raise KeyError(tf)


def tf_constants(tf, pivot):
    """(pivot code value, code values per stop, black code value)."""
    stop = tf_encode(2.0 * MIDGRAY, tf) - tf_encode(MIDGRAY, tf)
    return tf_encode(MIDGRAY * 2.0 ** pivot, tf), stop, tf_encode(0.0, tf)


def smooth01(x):
    t = min(max(x, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def di_decode(y):
    return 2.0 ** (min(y, 5.0) / STOP - 7.0) - 0.0075 if y > 0.02740668 else y / 10.44426855


def di_encode(x):
    return (math.log2(x + 0.0075) + 7.0) * STOP if x > 0.00262409 else x * 10.44426855


def cct_decode(y):
    return 2.0 ** (min(y, 4.0) * 17.52 - 9.72) if y > 0.155251141552511 else (y - 0.0729055341958355) / 10.5402377416545


def cct_encode(x):
    return 10.5402377416545 * x + 0.0729055341958355 if x <= 0.0078125 else (math.log2(x) + 9.72) / 17.52


def to_work(c, enc):
    if enc == "TF_LINEAR":
        return np.array([di_encode(v) for v in c])
    return np.array(c, dtype=float)


def from_work(y, enc):
    if enc == "TF_LINEAR":
        return np.array([di_decode(v) for v in y])
    return np.array(y)


def zone_offset(x, zones):
    t = min(max((x - ZONE_CENTRE0) / ZONE_STEP, 0.0), 4.0)
    i = min(int(math.floor(t)), 3)
    f = smooth01(t - i)
    return (1.0 - f) * zones[i] + f * zones[i + 1]


def tone(y, p, tf="TF_DI"):
    """Mirror of McpTone: y = code values (3), p = control dict."""
    y = np.array(y, dtype=float)
    zones = np.array(p["zones"], dtype=float).copy()
    if p["neutral"] > 0.0:
        zones[2] = zones[2] - p["neutral"] / 100.0 * (zones[2] - zones[2].mean())
    piv, stop, black = tf_constants(tf, p["pivot"])
    x = (float(np.dot(LUMA, y)) - piv) / stop
    o = zone_offset(x, zones) * (stop / 100.0)
    w = p["blend"] / 100.0
    x_black = min((black - piv) / stop, BLACK_TOP - BLACK_WIDTH)
    w *= 1.0 - p["clean_blacks"] / 100.0 * (1.0 - smooth01((x - x_black) / BLACK_WIDTH))
    w *= 1.0 - p["clean_whites"] / 100.0 * smooth01((x - WHITE_START) / WHITE_WIDTH)
    if p["sat_mask"] > 0.0:
        m = float(np.linalg.norm(y - y.mean()))
        w *= 1.0 - p["sat_mask"] / 100.0 * smooth01(m / (SAT_CHROMA * stop / STOP))
    return y + SCALE * w * o


def active(p):
    return bool(np.any(np.array(p["zones"]) != 0.0)) and p["blend"] != 0.0


def pixel(c, enc="TF_DI", **ui):
    p = dict(DEFAULTS, **ui)
    if not active(p):
        return tuple(c)
    return tuple(from_work(tone(to_work(c, enc), p, enc), enc))
