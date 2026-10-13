"""MC Pro Split - RGB split tone in five tonal zones: reference implementation.

MarkCaptures MC Pro Split - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Mirrors src/MC_Pro-Split.dctl.in.  Works directly on the log code values y
of the chosen Transfer Function (in whatever gamut the image is in), where
adding to a channel is an exposure shift of that channel.  Scene Linear is
worked on as DaVinci Intermediate.

    stop = TF(0.36) - TF(0.18)                      code values per stop
    x    = (luma(y) - TF(0.18 x 2^pivot)) / stop    brightness in stops
    Five broad, overlapping zones, Lo / Lo-Mid / Mid / Hi-Mid / Hi, between
    four soft boundaries at -1.875, -0.625, +0.625, +1.875 stops (logistic,
    width tau = 1.5 stops):
        F_j = 1 / (1 + exp(-(x - b_j) / tau))
        w_Lo = 1 - F_1, w_LoMid = F_1 - F_2, ..., w_Hi = F_4
    so the weights always sum to 1 (the same setting on all five zones is a
    plain offset), every zone peaks at its own centre, and each reaches well
    into its neighbours.
    y' = y + SCALE stop x slider / 100 x w x Blend x clean(x) x satmask

    The zone width and strength and the Clean Blacks law were fitted to curve
    measurements of a reference RGB split tone (Lo -100 at Clean Blacks 51,
    67 and 100): within about 0.005 code value.

    Neutral Pivot  keeps a band around the pivot neutral: the toning fades in
                   with smoothstep(|x| / h), h = 6.9 x slider / 100 stops
                   (31.8 = about 2.2 stops, matched to the reference)
    Clean Blacks   fades the toning in from the transfer function's black over
                   H = 10 (slider / 100)^1.7 stops (smoothstep): 100 = clean
                   up to about +5 stops, 50 = about 3 stops above black
    Clean Whites   the same, down from code value 1.0
    Sat Mask       fades it out on saturated colours (tones the neutrals)

A Clean fade or the Neutral Pivot band is never made steeper than the
strongest zone setting allows (below that the slider lowers its strength
instead), so a grey ramp does not reverse.
"""

import math

import numpy as np

STOP = 0.07329248             # DaVinci Intermediate log per stop (above the toe)
MIDGRAY = 0.18
SCALE = 1.8                   # offset in stops at zone weight 1 and slider 100
ZONES = ("Lo", "Lo-Mid", "Mid", "Hi-Mid", "Hi")
ZONE_CENTRE0, ZONE_STEP = -2.5, 1.25    # nominal centres (boundaries half way between)
ZONE_TAU = 1.5
CLEAN_HEIGHT, CLEAN_POWER = 9.97, 1.7   # fade height in stops = H (slider / 100)^P
CLEAN_MIN_STOPS = 3.0                   # minimum fade height at a zone slider of 100 (scales with the largest slider)
NEUTRAL_WIDTH = 6.9                     # Neutral Pivot band half width in stops at 100
NEUTRAL_GUARD = 1.65                    # band never steeper than 1.65 x the offset near the pivot (in stops)
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


def _logistic(t):
    return 1.0 / (1.0 + math.exp(-t)) if t > -60.0 else 0.0


def zone_weights(x):
    f = [_logistic((x - (ZONE_CENTRE0 + ZONE_STEP * (j + 0.5))) / ZONE_TAU) for j in range(4)]
    return np.array([1.0 - f[0], f[0] - f[1], f[1] - f[2], f[2] - f[3], f[3]])


def zone_offset(x, zones):
    return zone_weights(x) @ zones


def clean(d, amount, zmax=100.0):
    """fade-in weight at d stops from the black (or white) end"""
    if amount <= 0.0:
        return 1.0
    h = CLEAN_HEIGHT * (amount / 100.0) ** CLEAN_POWER
    hmin = max(CLEAN_MIN_STOPS * zmax / 100.0, 0.05)
    k = min(1.0, h / hmin)
    return 1.0 - k * (1.0 - smooth01(d / max(h, hmin)))


def neutral_band(x, amount, zones, stop):
    """the band's minimum width follows the zone offsets actually found around
    the pivot, so it can be as narrow as the reference without a ramp reversing"""
    if amount <= 0.0:
        return 1.0
    h = NEUTRAL_WIDTH * amount / 100.0
    m = max(float(np.abs(zone_offset(f * h, zones)).max()) for f in (-1.0, -0.5, 0.0, 0.5, 1.0))
    hmin = max(NEUTRAL_GUARD * m * SCALE / 100.0, 0.05)
    k = min(1.0, h / hmin)
    return 1.0 - k * (1.0 - smooth01(abs(x) / max(h, hmin)))


def tone(y, p, tf="TF_DI"):
    """Mirror of McpTone: y = code values (3), p = control dict."""
    y = np.array(y, dtype=float)
    zones = np.array(p["zones"], dtype=float)
    zmax = float(np.abs(zones).max())
    piv, stop, black = tf_constants(tf, p["pivot"])
    x = (float(np.dot(LUMA, y)) - piv) / stop
    o = zone_offset(x, zones) * (stop / 100.0)
    w = p["blend"] / 100.0
    w *= clean(x - (black - piv) / stop, p["clean_blacks"], zmax)
    w *= clean((1.0 - piv) / stop - x, p["clean_whites"], zmax)
    w *= neutral_band(x, p["neutral"], zones, stop)
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
