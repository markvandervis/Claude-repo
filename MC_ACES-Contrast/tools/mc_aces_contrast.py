"""
MC ACES Contrast - reference model.

MarkCaptures MC ACES Contrast
(c) 2026 Mark van der Vis / MarkCaptures - www.markcaptures.com
All rights reserved; see ../LICENSE.txt.

The "Contrast" compound node of Mark's PowerGrade, rebuilt as one DCTL.  The
nodes, their settings and the order of the node graph are read from the
PowerGrade (.drx); Density and Sat. Fix are Color Warper / Chroma-Luma nodes
whose look is carried by 65-point LUTs exported from Resolve (wrapped as
DWG/DI -> ACEScct -> node -> DWG/DI, so they are applied in DWG/DI).

    input  DaVinci Wide Gamut / DaVinci Intermediate (or ACEScct)
      -> ACEScct (AP1)
      1 Diffusion        custom curve, Y=R=G=B
      2 Density          LUT (DWG/DI)
      3 Compensation     HDR global exposure -0.30 stop (linear)
      4 Hue Adjustments  Hue vs Hue and Hue vs Sat curves
      5 Midtones         contrast 1.1 @ 0.435 and HDR saturation 0.9,
                         inside a luminance key (58.3 - 61.4 %)
      6 Contrast         custom curve, Y=R=G=B
      7 Shadows          blue curve inside an inverted luminance key (gain 0.8)
      8 Sat. Fix         LUT (DWG/DI)
      extras: contrast / pivot, saturation, exposure, blend
      -> back to the input space

Every node has a strength in % (out = in + k (node(in) - in)); at the defaults
the DCTL reproduces the PowerGrade node by node.

This module is the source of truth: build_dctl.py turns its tables into the
DCTL, and the tests run the generated DCTL against pixel() here.
"""
import os
import numpy as np

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LUT_FILES = {"density": "MC_ACES_Contrast_Density.cube", "satfix": "MC_ACES_Contrast_SatFix.cube"}

# ---------------------------------------------------------------------------
#  Colour spaces
# ---------------------------------------------------------------------------
# ACES AP1 -> DaVinci Wide Gamut (Bradford-adapted, as Resolve's CST); checked
# against Mark's exported Compensation LUT (an exact -0.30 stop exposure).
AP1_TO_DWG = np.array([[0.9146300837, 0.0044513140, 0.0809186011],
                       [0.0307714752, 0.7847643006, 0.1844642225],
                       [0.0674014105, 0.0829089888, 0.8496895932]])
DWG_TO_AP1 = np.linalg.inv(AP1_TO_DWG)
AP1_Y = np.array([0.2722287168, 0.6740817658, 0.0536895174])   # AP1 luminance
LUMA = np.array([0.2126, 0.7152, 0.0722])                      # qualifier luma (on ACEScct code)

DI_A, DI_B, DI_C, DI_M, DI_LIN_CUT, DI_LOG_CUT = 0.0075, 7.0, 0.07329248, 10.44426855, 0.00262409, 0.02740668
CCT_A, CCT_B, CCT_LIN_CUT, CCT_LOG_CUT = 10.5402377416545, 0.0729055341958355, 0.0078125, 0.155251141552511


def di_dec(y):
    y = np.asarray(y, dtype=float)
    return np.where(y > DI_LOG_CUT, np.exp2(np.minimum(y, 6.0) / DI_C - DI_B) - DI_A, y / DI_M)


def di_enc(x):
    x = np.asarray(x, dtype=float)
    return np.where(x > DI_LIN_CUT, (np.log2(np.maximum(x + DI_A, 1e-30)) + DI_B) * DI_C, x * DI_M)


def cct_enc(x):
    x = np.asarray(x, dtype=float)
    return np.where(x <= CCT_LIN_CUT, CCT_A * x + CCT_B, (np.log2(np.maximum(x, 1e-30)) + 9.72) / 17.52)


def cct_dec(y):
    y = np.asarray(y, dtype=float)
    return np.where(y > CCT_LOG_CUT, np.exp2(np.minimum(y, 6.0) * 17.52 - 9.72), (y - CCT_B) / CCT_A)


def dwg_to_cct(c):
    return cct_enc(di_dec(c) @ DWG_TO_AP1.T)


def cct_to_dwg(c):
    return di_enc(cct_dec(c) @ AP1_TO_DWG.T)


# ---------------------------------------------------------------------------
#  Node data, as read from the PowerGrade
# ---------------------------------------------------------------------------
# Custom curves: control points in Resolve's 0..1023 code (x, y); the black
# end point (0, 0) is implicit.  Linked Y/R/G/B curves act once per channel.
DIFFUSION = ((341.0, 308.240204), (679.67395, 643.54895), (1023.0, 924.72052))
CONTRAST = ((148.865677, 125.49894), (221.445312, 221.445343), (276.335602, 276.240356),
            (420.085938, 446.234406), (449.394287, 476.590515), (552.671204, 567.658752),
            (699.673401, 699.67334), (834.417847, 816.099243), (1023.0, 1023.0))
SHADOWS_B = ((72.107773, 92.080124), (133.493973, 193.671707), (216.323334, 276.240356),
             (275.045868, 334.778046), (359.234741, 362.592316), (420.085938, 418.91394),
             (628.873352, 612.15979), (822.028625, 821.637939), (1023.0, 1023.0))

# Hue curves: periodic cubic Bezier, stored as P, c, c, P, c, c, P ...;
# x = hue in turns (0 red, 1/3 green, 2/3 blue), y = 0.5 neutral.
# Hue vs Hue shifts hue by (y - 0.5) turn, Hue vs Sat scales chroma by 2y.
HUE_HUE = ((-0.360689, 0.479233), (-0.26689, 0.488187), (-0.266422, 0.494411), (-0.172239, 0.497222),
           (-0.079221, 0.499998), (0.25927, 0.497247), (0.33536, 0.5), (0.407248, 0.502601),
           (0.407295, 0.520767), (0.47923, 0.520767), (0.559271, 0.520767), (0.559271, 0.479233),
           (0.639311, 0.479233), (0.733536, 0.479233), (0.733578, 0.494411), (0.827761, 0.497222),
           (0.920779, 0.499998), (1.25927, 0.497247), (1.33536, 0.5), (1.407248, 0.502601),
           (1.408033, 0.51049), (1.47923, 0.520767))
HUE_SAT = ((-0.358663, 0.4377), (-0.270786, 0.467227), (-0.265697, 0.493051), (-0.173252, 0.5),
           (-0.162105, 0.500838), (0.162107, 0.501597), (0.497467, 0.501597), (0.569402, 0.501597),
           (0.569402, 0.4377), (0.641337, 0.4377), (0.734043, 0.4377), (0.734303, 0.493051),
           (0.826748, 0.5), (0.837895, 0.500838), (1.162107, 0.501597), (1.497467, 0.501597),
           (1.569402, 0.501597), (1.575595, 0.466898), (1.641337, 0.4377))
HUE_PERIOD_START = 3          # control point P1: one full period of segments starts here

# Midtones: Primaries contrast 1.1 around pivot 0.435 (ACEScct), HDR Global
# saturation 0.9 (ACES), inside a luminance qualifier.
MT_CONTRAST, MT_PIVOT, MT_SAT = 1.1, 0.435, 0.9
MT_LOW, MT_HIGH = 0.583216667175293, 0.6139860153198242
MT_LOW_SOFT, MT_HIGH_SOFT = 0.03356635570526123, 0.013985991477966309
# The PowerGrade softens this key spatially (Denoise 100), which a per-pixel
# DCTL cannot do: with the stored softness the contrast would fold the grey
# ramp back at the key's edge.  The edges are widened just enough to keep the
# slope of the tone curve at or above about 0.3:  soft >= MT_SOFT_K * |shift|.
MT_SOFT_K = 2.5
MT_SOFT_MARGIN = 0.05

# Shadows: blue curve; luminance qualifier 55.7 - 99.0 % (low soft 4.76 %),
# inverted, key gain 0.8.
SH_LOW, SH_HIGH, SH_LOW_SOFT, SH_HIGH_SOFT = 0.5566433072090149, 0.9902098178863525, 0.04755258560180664, 0.0
SH_GAIN = 0.8

COMPENSATION = -0.30          # stops, HDR Global exposure (linear)

DEFAULTS = dict(blend=100.0, diffusion=100.0, density=100.0, compensation=COMPENSATION, hue=100.0,
                midtones=100.0, contrast_curve=100.0, shadows=100.0, satfix=100.0,
                contrast=1.0, pivot=0.4135, saturation=1.0, exposure=0.0, bypass=0, space=0)
SPACES = ("DaVinci Wide Gamut Intermediate", "ACEScct")


# ---------------------------------------------------------------------------
#  Curves
# ---------------------------------------------------------------------------
def mono_knots(points, scale=1023.0):
    """Monotone (Fritsch-Carlson) cubic through (0,0) and the points."""
    p = sorted(points)
    x = np.array([0.0] + [a / scale for a, _ in p])
    y = np.array([0.0] + [b / scale for _, b in p])
    d = np.diff(y) / np.diff(x)
    m = np.empty_like(x)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:   # weighted harmonic mean (Fritsch-Butland), monotone and C1
            h0, h1 = x[i] - x[i - 1], x[i + 1] - x[i]
            w0, w1 = 2 * h1 + h0, h1 + 2 * h0
            m[i] = (w0 + w1) / (w0 / d[i - 1] + w1 / d[i])
    return x, y, m


def mono_eval(knots, v):
    x, y, m = knots
    v = np.asarray(v, dtype=float)
    out = np.empty_like(v)
    lo, hi = v < x[0], v > x[-1]
    out[lo] = y[0] + m[0] * (v[lo] - x[0])
    out[hi] = y[-1] + m[-1] * (v[hi] - x[-1])
    mid = ~(lo | hi)
    vm = v[mid]
    i = np.clip(np.searchsorted(x, vm, side="right") - 1, 0, len(x) - 2)
    h = x[i + 1] - x[i]
    t = (vm - x[i]) / h
    t2, t3 = t * t, t * t * t
    out[mid] = ((2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h * m[i]
                + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h * m[i + 1])
    return out


KN_DIFFUSION = mono_knots(DIFFUSION)
KN_CONTRAST = mono_knots(CONTRAST)
KN_SHADOWS = mono_knots(SHADOWS_B)


def bezier_periodic(points, start=HUE_PERIOD_START):
    """One period of a periodic cubic Bezier: list of segments (P0, c1, c2, P1)."""
    p = np.array(points, dtype=float)
    segs, x0 = [], p[start, 0]
    i = start
    while i + 3 < len(p) and p[i, 0] < x0 + 1.0 - 1e-9:
        segs.append(p[i:i + 4])
        i += 3
    assert abs(segs[-1][3][0] - (x0 + 1.0)) < 1e-4, "hue curve is not periodic"
    return x0, segs


def bezier_eval(curve, h):
    """y of a periodic Bezier curve at hue h (turns); x(t) is solved by bisection."""
    x0, segs = curve
    h = np.asarray(h, dtype=float)
    u = x0 + np.mod(h - x0, 1.0)
    out = np.full(u.shape, 0.5)
    for s in segs:
        sel = (u >= s[0, 0]) & (u <= s[3, 0])
        if not sel.any():
            continue
        uu = u[sel]
        a, b = np.zeros_like(uu), np.ones_like(uu)
        for _ in range(48):
            t = 0.5 * (a + b)
            q = 1 - t
            xt = q ** 3 * s[0, 0] + 3 * q * q * t * s[1, 0] + 3 * q * t * t * s[2, 0] + t ** 3 * s[3, 0]
            right = xt < uu
            a, b = np.where(right, t, a), np.where(right, b, t)
        t = 0.5 * (a + b)
        q = 1 - t
        out[sel] = q ** 3 * s[0, 1] + 3 * q * q * t * s[1, 1] + 3 * q * t * t * s[2, 1] + t ** 3 * s[3, 1]
    return out


BZ_HUE_HUE = bezier_periodic(HUE_HUE)
BZ_HUE_SAT = bezier_periodic(HUE_SAT)


# ---------------------------------------------------------------------------
#  Exported LUTs (DWG/DI -> DWG/DI), tetrahedral like the DCTL
# ---------------------------------------------------------------------------
def load_cube(path):
    n, rows = None, []
    with open(path) as fh:
        for line in fh:
            s = line.split()
            if not s or s[0].startswith("#"):
                continue
            if s[0] == "LUT_3D_SIZE":
                n = int(s[1])
            elif s[0][0].isdigit() or s[0][0] in "-.":
                rows.append([float(v) for v in s[:3]])
    a = np.array(rows, dtype=float)
    assert n is not None and len(a) == n ** 3, path
    return a.reshape(n, n, n, 3)          # [b][g][r]


_LUTS = {}


def lut(name):
    if name not in _LUTS:
        _LUTS[name] = load_cube(os.path.join(ROOT, LUT_FILES[name]))
    return _LUTS[name]


def lut_vertex(L, r, g, b):
    return L[b, g, r]


def apply_lut(L, c):
    """Tetrahedral lookup of clamp(c, 0, 1).  The DCTL does the same with four
    APPLY_LUT reads at lattice points, so it does not depend on how the host
    interpolates (a grey stays on the LUT's own grey axis)."""
    n = L.shape[0]
    p = np.clip(c, 0.0, 1.0) * (n - 1)
    i = np.minimum(np.floor(p).astype(int), n - 2)
    f = p - i
    fr, fg, fb = f[..., 0], f[..., 1], f[..., 2]
    r, g, b = i[..., 0], i[..., 1], i[..., 2]
    one = np.ones_like(r)
    zero = np.zeros_like(r)
    # (first axis, second axis, f1, f2, f3) for the six orderings, as in the DCTL
    cases = [
        ((fr > fg) & (fg > fb), (one, zero, zero), (one, one, zero), fr, fg, fb),
        ((fr > fg) & ~(fg > fb) & (fr > fb), (one, zero, zero), (one, zero, one), fr, fb, fg),
        ((fr > fg) & ~(fg > fb) & ~(fr > fb), (zero, zero, one), (one, zero, one), fb, fr, fg),
        (~(fr > fg) & (fb > fg), (zero, zero, one), (zero, one, one), fb, fg, fr),
        (~(fr > fg) & ~(fb > fg) & (fb > fr), (zero, one, zero), (zero, one, one), fg, fb, fr),
        (~(fr > fg) & ~(fb > fg) & ~(fb > fr), (zero, one, zero), (one, one, zero), fg, fr, fb),
    ]
    out = np.zeros(c.shape, dtype=float)
    v0 = lut_vertex(L, r, g, b)
    v3 = lut_vertex(L, r + 1, g + 1, b + 1)
    for sel, a1, a2, f1, f2, f3 in cases:
        v1 = lut_vertex(L, r + a1[0], g + a1[1], b + a1[2])
        v2 = lut_vertex(L, r + a2[0], g + a2[1], b + a2[2])
        o = ((1 - f1)[..., None] * v0 + (f1 - f2)[..., None] * v1
             + (f2 - f3)[..., None] * v2 + f3[..., None] * v3)
        out = np.where(sel[..., None], o, out)
    return out


def lut_node(name, dwg, k):
    """out = in + k (LUT(in) - in), on clamped input so out-of-range values pass through."""
    cl = np.clip(dwg, 0.0, 1.0)
    return dwg + k * (apply_lut(lut(name), cl) - cl)


# ---------------------------------------------------------------------------
#  Nodes (ACEScct in, ACEScct out unless noted)
# ---------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    if e1 <= e0:
        return (x >= e1).astype(float)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def curve_node(kn, c, k, channels=(0, 1, 2)):
    out = c.copy()
    for ch in channels:
        out[..., ch] = c[..., ch] + k * (mono_eval(kn, c[..., ch]) - c[..., ch])
    return out


def hsv_hue(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn
    ds = np.where(d > 1e-10, d, 1.0)
    h = np.where(mx == r, (g - b) / ds, np.where(mx == g, 2.0 + (b - r) / ds, 4.0 + (r - g) / ds))
    return np.mod(h / 6.0, 1.0)


def rotate_neutral(v, ang):
    """Rotate vectors v (chroma, mean 0) by ang radians about the neutral axis."""
    cs, sn = np.cos(ang)[..., None], np.sin(ang)[..., None]
    u = np.ones(3) / np.sqrt(3.0)
    cross = np.cross(np.broadcast_to(u, v.shape), v)
    return v * cs + cross * sn            # u . v = 0 for chroma vectors


def hue_node(c, k):
    if k == 0:
        return c.copy()
    h = hsv_hue(c)
    dh = bezier_eval(BZ_HUE_HUE, h) - 0.5
    g = 2.0 * bezier_eval(BZ_HUE_SAT, h)
    m = c.mean(axis=-1, keepdims=True)
    v = rotate_neutral(c - m, 2 * np.pi * k * dh)
    return m + v * (1.0 + k * (g - 1.0))[..., None]


def soft_edges(k, low, high, low_soft, high_soft):
    d_lo = abs(k * (MT_CONTRAST - 1.0) * (low - MT_PIVOT))
    d_hi = abs(k * (MT_CONTRAST - 1.0) * (high + MT_SOFT_MARGIN - MT_PIVOT))
    return max(low_soft, MT_SOFT_K * d_lo), max(high_soft, MT_SOFT_K * d_hi)


def midtones_node(c, k):
    if k == 0:
        return c.copy()
    ls, hs = soft_edges(k, MT_LOW, MT_HIGH, MT_LOW_SOFT, MT_HIGH_SOFT)
    y = c @ LUMA
    key = smoothstep(MT_LOW - ls, MT_LOW, y) * (1.0 - smoothstep(MT_HIGH, MT_HIGH + hs, y))
    x1 = (c - MT_PIVOT) * MT_CONTRAST + MT_PIVOT
    lin = cct_dec(x1)
    yl = (lin @ AP1_Y)[..., None]
    x2 = cct_enc(yl + MT_SAT * (lin - yl))
    return c + (k * key)[..., None] * (x2 - c)


def shadows_node(c, k):
    if k == 0:
        return c.copy()
    y = c @ LUMA
    sel = smoothstep(SH_LOW - SH_LOW_SOFT, SH_LOW, y) * (1.0 - smoothstep(SH_HIGH, SH_HIGH + SH_HIGH_SOFT, y))
    key = SH_GAIN * (1.0 - sel)
    out = c.copy()
    b = c[..., 2]
    out[..., 2] = b + k * key * (mono_eval(KN_SHADOWS, b) - b)
    return out


def extras(c, contrast, pivot, saturation, exposure):
    if contrast != 1.0:
        c = (c - pivot) * contrast + pivot
    if saturation != 1.0 or exposure != 0.0:
        lin = cct_dec(c) * 2.0 ** exposure
        if saturation != 1.0:
            yl = (lin @ AP1_Y)[..., None]
            lin = yl + saturation * (lin - yl)
        c = cct_enc(lin)
    return c


def pixel(rgb, **kw):
    """The whole node, on an array of pixels (..., 3) in the chosen space."""
    p = dict(DEFAULTS)
    unknown = set(kw) - set(p)
    assert not unknown, unknown
    p.update(kw)
    src = np.array(rgb, dtype=float)
    if p["bypass"]:
        return src.copy()
    s = lambda v: p[v] / 100.0
    cct = dwg_to_cct(src) if p["space"] == 0 else src.copy()

    cct = curve_node(KN_DIFFUSION, cct, s("diffusion"))
    dwg = lut_node("density", cct_to_dwg(cct), s("density"))
    lin = di_dec(dwg) * 2.0 ** p["compensation"]
    cct = cct_enc(lin @ DWG_TO_AP1.T)
    cct = hue_node(cct, s("hue"))
    cct = midtones_node(cct, s("midtones"))
    cct = curve_node(KN_CONTRAST, cct, s("contrast_curve"))
    cct = shadows_node(cct, s("shadows"))
    dwg = lut_node("satfix", cct_to_dwg(cct), s("satfix"))

    if p["contrast"] != 1.0 or p["saturation"] != 1.0 or p["exposure"] != 0.0:
        dwg = cct_to_dwg(extras(dwg_to_cct(dwg), p["contrast"], p["pivot"], p["saturation"], p["exposure"]))
    out = dwg if p["space"] == 0 else dwg_to_cct(dwg)
    return src + s("blend") * (out - src)


# ---------------------------------------------------------------------------
#  Tables for the DCTL
# ---------------------------------------------------------------------------
CURVE_N = 1025          # samples of each tone curve over code 0 .. 1
HUE_N = 512             # samples of each hue curve over one turn


def curve_table(kn):
    return mono_eval(kn, np.linspace(0.0, 1.0, CURVE_N))


def hue_table(bz):
    return bezier_eval(bz, np.arange(HUE_N) / HUE_N)
