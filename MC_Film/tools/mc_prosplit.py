"""MC Pro Split - RGB split tone in five tonal zones: reference implementation.

MarkCaptures MC Pro Split - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Mirrors src/MC_Pro-Split.dctl.in.  Works in DaVinci Wide Gamut, on the
DaVinci Intermediate log value y of each channel, where adding to a channel is
an exposure shift of that channel.

    x  = (luma(y) - DI(0.184 x 2^pivot)) / stop     brightness in stops
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
MIDGRAY = 0.184
SCALE = 0.034                 # log offset at a zone slider of 1 (about half a stop)
ZONES = ("Lo", "Lo-Mid", "Mid", "Hi-Mid", "Hi")
ZONE_CENTRE0, ZONE_STEP = -4.0, 2.0
# Clean Blacks / Whites fade zones, in DaVinci Intermediate stops from the
# pivot (black, code 0, is at x = -4.6 for the default pivot)
BLACK_START, BLACK_WIDTH = -4.6, 2.5
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

ENCODINGS = [("PS_DWG", "DaVinci WG Intermediate"), ("PS_ACESCCT", "ACES AP1 ACEScct"),
             ("PS_LINEAR", "Scene Linear Rec709"), ("PS_709", "Rec709 Gamma 2.4")]

DEFAULTS = dict(zones=np.zeros((5, 3)), blend=100.0, pivot=0.0, neutral=0.0, clean_blacks=30.0,
                clean_whites=30.0, sat_mask=0.0)


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
    if enc == "PS_DWG":
        return np.array(c, dtype=float)
    if enc == "PS_ACESCCT":
        lin = AP1_TO_DWG @ np.array([cct_decode(v) for v in c])
    elif enc == "PS_LINEAR":
        lin = REC709_TO_DWG @ np.array(c, dtype=float)
    else:
        lin = REC709_TO_DWG @ np.array([max(v, 0.0) ** 2.4 for v in c])
    return np.array([di_encode(v) for v in lin])


def from_work(y, enc):
    if enc == "PS_DWG":
        return np.array(y)
    lin = np.array([di_decode(v) for v in y])
    if enc == "PS_ACESCCT":
        return np.array([cct_encode(v) for v in DWG_TO_AP1 @ lin])
    lin = DWG_TO_REC709 @ lin
    if enc == "PS_LINEAR":
        return lin
    return np.array([max(v, 0.0) ** (1.0 / 2.4) for v in lin])


def zone_offset(x, zones):
    t = min(max((x - ZONE_CENTRE0) / ZONE_STEP, 0.0), 4.0)
    i = min(int(math.floor(t)), 3)
    f = smooth01(t - i)
    return (1.0 - f) * zones[i] + f * zones[i + 1]


def tone(y, p):
    """Mirror of McpTone: y = DI log of DWG (3), p = control dict."""
    y = np.array(y, dtype=float)
    zones = np.array(p["zones"], dtype=float).copy()
    if p["neutral"] > 0.0:
        zones[2] = zones[2] - p["neutral"] / 100.0 * (zones[2] - zones[2].mean())
    x = (float(np.dot(LUMA, y)) - di_encode(MIDGRAY * 2.0 ** p["pivot"])) / STOP
    o = zone_offset(x, zones)
    w = p["blend"] / 100.0
    w *= 1.0 - p["clean_blacks"] / 100.0 * (1.0 - smooth01((x - BLACK_START) / BLACK_WIDTH))
    w *= 1.0 - p["clean_whites"] / 100.0 * smooth01((x - WHITE_START) / WHITE_WIDTH)
    if p["sat_mask"] > 0.0:
        m = float(np.linalg.norm(y - y.mean()))
        w *= 1.0 - p["sat_mask"] / 100.0 * smooth01(m / SAT_CHROMA)
    return y + SCALE * w * o


def active(p):
    return bool(np.any(np.array(p["zones"]) != 0.0)) and p["blend"] != 0.0


def pixel(c, enc="PS_DWG", **ui):
    p = dict(DEFAULTS, **ui)
    if not active(p):
        return tuple(c)
    return tuple(from_work(tone(to_work(c, enc), p), enc))
