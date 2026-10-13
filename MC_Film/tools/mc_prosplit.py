"""MC Pro Split - split tone / crossover: reference implementation.

MarkCaptures MC Pro Split - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Mirrors src/MC_Pro-Split.dctl.in.  Works in DaVinci Wide Gamut, on the
DaVinci Intermediate log value of each channel (y).  A split tone is a
per-channel log offset - an exposure shift per channel - that changes with
the brightness of the pixel:

    x   = (luma(y) - pivot) / stop           brightness in stops from mid grey
    ws  = S((-x - hold) / width)             shadow zone   (S = smoothstep)
    wh  = S(( x - hold) / width)             highlight zone
    o   = XS A (ks ws - kh wh) dir(hue) + CS C dir(cast hue)
          x black-neutral weight x (1 - skin preserve x skin weight)

dir(h) is a unit vector in the chroma plane (zero sum, so greys stay grey in
mean): shadows go towards the crossover hue, highlights towards its
complement.  Desat Protect removes the part of o that points against a
colour's own chroma (it would desaturate it); Shadow / Highlight Hue Twist
rotate the chroma in each zone.  The zone weights rise at most 1.5 / width
per stop, so with XS and the minimum width the offset changes by less than
the brightness itself: a grey ramp can never reverse.
"""

import math

import numpy as np

STOP = 0.07329248             # DaVinci Intermediate log per stop (above the toe)
MIDGRAY = 0.184
XOVER_SCALE = 0.035           # log offset at Crossover Amount 1 (about half a stop)
CAST_SCALE = 0.03             # log offset at Cast Amount 1
MID_RANGE = 2.0               # Middle Grey +-1 = +-2 stops
HOLD_MAX = 1.5                # Midtone Hold 1 = +-1.5 stops untouched
WIDTH_MIN, WIDTH_RANGE = 1.25, 2.75  # Crossover Knee 0 .. 1 = 1.25 .. 4 stops of transition
# Black Neutral fades the toning out towards black.  x is measured in DaVinci
# Intermediate stops, which reach black (code 0) at x = -4.6 from 18 % grey;
# the fade starts at x = -2.1, about 2.3 real stops below grey.
BLACK_START, BLACK_WIDTH = -4.6, 2.5
TWIST_MAX = 60.0              # degrees at Hue Twist +-1
DESAT_CHROMA = 0.06           # chroma (log) at which Desat Protect is fully on
SKIN_HUE, SKIN_WIDTH, SKIN_CHROMA = 25.0, 22.0, 0.04
LUMA = (0.30, 0.60, 0.10)

E1 = np.array([2.0, -1.0, -1.0]) / math.sqrt(6.0)
E2 = np.array([0.0, 1.0, -1.0]) / math.sqrt(2.0)

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

DEFAULTS = dict(amount=0.0, hue=0.55, desat=0.5, balance=0.0, mid=0.0, hold=0.0, knee=0.5, black=0.5,
                cast=0.0, cast_hue=0.08, twist_s=0.0, twist_h=0.0, skin=0.5)


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
    """input encoding -> DaVinci Intermediate log of DWG."""
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


def direction(h):
    a = 2.0 * math.pi * h
    return math.cos(a) * E1 + math.sin(a) * E2


def rotate(c, deg):
    a = math.radians(deg)
    k = np.ones(3) / math.sqrt(3.0)
    return c * math.cos(a) + np.cross(k, c) * math.sin(a)


def tone(y, p):
    """Mirror of McpTone: y = DI log of DWG (3), p = control dict."""
    y = np.array(y, dtype=float)
    lum = float(np.dot(LUMA, y))
    x = (lum - di_encode(MIDGRAY * 2.0 ** (MID_RANGE * p["mid"]))) / STOP
    hw, width = p["hold"] * HOLD_MAX, WIDTH_MIN + WIDTH_RANGE * p["knee"]
    ws, wh = smooth01((-x - hw) / width), smooth01((x - hw) / width)
    ks, kh = min(1.0, 1.0 - p["balance"]), min(1.0, 1.0 + p["balance"])
    mean = y.mean()
    c = y - mean
    m = float(np.linalg.norm(c))
    skin = 0.0
    if p["skin"] > 0.0 and m > 1e-9:
        hue = math.degrees(math.atan2(float(c @ E2), float(c @ E1)))
        dh = (hue - SKIN_HUE + 180.0) % 360.0 - 180.0
        skin = smooth01(m / SKIN_CHROMA) * math.exp(-(dh / SKIN_WIDTH) ** 2) * smooth01((x + 5.0) / 2.0)
    keep = 1.0 - p["skin"] * skin
    if p["twist_s"] != 0.0 or p["twist_h"] != 0.0:
        c = rotate(c, (ws * p["twist_s"] + wh * p["twist_h"]) * TWIST_MAX * keep)
    wb = 1.0 - p["black"] * (1.0 - smooth01((x - BLACK_START) / BLACK_WIDTH))
    o = (XOVER_SCALE * p["amount"] * (ks * ws - kh * wh) * direction(p["hue"]) +
         CAST_SCALE * p["cast"] * direction(p["cast_hue"])) * wb * keep
    if p["desat"] > 0.0 and m > 1e-9:
        u = c / max(np.linalg.norm(c), 1e-12)
        proj = float(o @ u)
        if proj < 0.0:
            o = o - p["desat"] * smooth01(m / DESAT_CHROMA) * proj * u
    return mean + c + o


def active(p):
    return p["amount"] != 0.0 or p["cast"] != 0.0 or p["twist_s"] != 0.0 or p["twist_h"] != 0.0


def pixel(c, enc="PS_DWG", **ui):
    p = dict(DEFAULTS, **ui)
    if not active(p):
        return tuple(c)
    return tuple(from_work(tone(to_work(c, enc), p), enc))
