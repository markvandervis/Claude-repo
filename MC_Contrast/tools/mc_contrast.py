"""
MC Contrast - reference model.

MarkCaptures MC Contrast
(c) 2026 Mark van der Vis / MarkCaptures - www.markcaptures.com
All rights reserved; see ../LICENSE.txt.

The "Contrast" compound node of Mark's PowerGrade, rebuilt as one DCTL.  The
nodes and their order are read from the PowerGrade (.drx).  Every node except
Midtones is carried by Resolve's own 65-point LUT of it, exported wrapped as
DWG/DI -> ACEScct -> node -> DWG/DI, so they are applied in DWG/DI; Diffusion
is a pure per-channel curve, so it is taken from its LUT's grey axis as a 1D
curve.  Midtones is rebuilt from its settings, because its key is spatial
(Denoise 100) and its LUT export holds almost nothing.

    input  DaVinci Wide Gamut / DaVinci Intermediate (or ACEScct)
      -> ACEScct (AP1)
      1 Diffusion        per-channel curve (measured from its LUT)
      2 Density          LUT
      3 Compensation     HDR global exposure -0.30 stop (linear)
      4 Hue Adjustments  LUT
      5 Midtones         contrast 1.1 @ 0.435 and HDR saturation 0.9,
                         inside a luminance key (58.3 - 61.4 %)
      6 Contrast         LUT
      7 Shadows          LUT (its key included, per pixel)
      8 Sat. Fix         LUT
      extras: contrast / pivot, saturation, exposure, blend
      -> back to the input space

Every node has a strength in % (out = in + k (node(in) - in)); at the defaults
the DCTL reproduces the PowerGrade node by node.

v1.0 rebuilt Diffusion, Hue Adjustments, Contrast and Shadows from the curve
points stored in the .drx.  Resolve's exports showed its curves do not pass
through those points (they behave like a Bezier/B-spline over them), which
crushed the shadows by up to a stop; v1.1 uses the measured nodes instead.

This module is the source of truth: build_dctl.py turns its tables into the
DCTL, and the tests run the generated DCTL against pixel() here.
"""
import os
import numpy as np

VERSION = "1.1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LUT_DIR = "MarkCaptures/source"            # relative to the DCTL, as DEFINE_LUT reads it
LUT_FILES = {"density": "MC_Contrast_Density.cube", "hue": "MC_Contrast_Hue.cube",
             "contrast": "MC_Contrast_Contrast.cube", "shadows": "MC_Contrast_Shadows.cube",
             "satfix": "MC_Contrast_SatFix.cube"}

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
# Diffusion: the grey axis of Resolve's LUT of the node, as (ACEScct in, out);
# the node is a linked Y/R/G/B curve and acts per channel (checked on colours:
# error < 0.001).  Below the first point the curve runs straight to (0, 0).
DIFFUSION_MEASURED = (
    (0.088674, 0.080544), (0.104514, 0.095111), (0.122136, 0.111395), (0.142565, 0.130153),
    (0.165572, 0.151653), (0.186803, 0.171277), (0.20606, 0.189209), (0.223888, 0.205682),
    (0.240645, 0.221301), (0.256575, 0.236156), (0.271856, 0.250394), (0.286619, 0.264201),
    (0.300961, 0.27771), (0.314959, 0.290722), (0.328674, 0.303474), (0.342153, 0.316232),
    (0.355436, 0.328557), (0.368554, 0.340732), (0.381533, 0.353001), (0.394394, 0.364921),
    (0.407155, 0.376975), (0.419831, 0.388709), (0.432435, 0.400391), (0.444977, 0.412182),
    (0.457467, 0.42372), (0.469911, 0.435433), (0.482317, 0.446876), (0.494689, 0.458494),
    (0.507033, 0.469855), (0.519353, 0.481414), (0.531652, 0.492691), (0.543932, 0.504184),
    (0.556197, 0.515415), (0.568449, 0.526844), (0.580689, 0.538028), (0.592919, 0.549389),
    (0.60514, 0.560523), (0.617355, 0.571838), (0.629562, 0.582929), (0.641765, 0.593976),
    (0.653963, 0.605231), (0.666156, 0.616228), (0.678346, 0.627436), (0.690533, 0.638388),
    (0.702718, 0.649527), (0.7149, 0.660461), (0.727081, 0.671509), (0.739259, 0.682353),
    (0.751436, 0.693385), (0.763612, 0.704166), (0.775787, 0.715147), (0.787961, 0.725865),
    (0.800135, 0.736782), (0.812307, 0.747438), (0.824479, 0.758283), (0.83665, 0.768889),
    (0.848821, 0.779661), (0.860992, 0.790183), (0.873162, 0.800905), (0.885332, 0.811343),
    (0.897502, 0.821993), (0.909672, 0.83237), (0.921841, 0.842913), (0.93401, 0.853229))
DIFFUSION_SMOOTH = 1e-5       # smoothing of the LUT's 1e-4 rounding wobble

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

COMPENSATION = -0.30          # stops, HDR Global exposure (linear)

DEFAULTS = dict(blend=100.0, diffusion=100.0, density=100.0, compensation=COMPENSATION, hue=100.0,
                midtones=100.0, contrast_curve=100.0, shadows=100.0, satfix=100.0,
                contrast=1.0, pivot=0.4135, saturation=1.0, exposure=0.0, bypass=0, space=0)
SPACES = ("DaVinci Wide Gamut Intermediate", "ACEScct")


# ---------------------------------------------------------------------------
#  Curves
# ---------------------------------------------------------------------------
def _diffusion_spline():
    from scipy.interpolate import make_smoothing_spline
    p = np.array(DIFFUSION_MEASURED)
    return make_smoothing_spline(p[:, 0], p[:, 1], lam=DIFFUSION_SMOOTH)


_DIFF = _diffusion_spline()
_DIFF_X0, _DIFF_X1 = DIFFUSION_MEASURED[0][0], DIFFUSION_MEASURED[-1][0]
DIFFUSION_M0 = float(_DIFF(_DIFF_X0)) / _DIFF_X0                 # slope of the straight run to (0, 0)
DIFFUSION_M1 = float(_DIFF.derivative()(_DIFF_X1))               # end slope above the last point


def diffusion_curve(v):
    v = np.asarray(v, dtype=float)
    out = np.where(v < _DIFF_X0, DIFFUSION_M0 * v,
                   np.where(v > _DIFF_X1, float(_DIFF(_DIFF_X1)) + DIFFUSION_M1 * (v - _DIFF_X1),
                            _DIFF(np.clip(v, _DIFF_X0, _DIFF_X1))))
    return out


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
        _LUTS[name] = load_cube(os.path.join(ROOT, LUT_DIR, LUT_FILES[name]))
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


def curve_node(f, c, k):
    return c + k * (f(c) - c)


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

    cct = curve_node(diffusion_curve, cct, s("diffusion"))
    dwg = lut_node("density", cct_to_dwg(cct), s("density"))
    dwg = di_enc(di_dec(dwg) * 2.0 ** p["compensation"])
    dwg = lut_node("hue", dwg, s("hue"))
    cct = midtones_node(dwg_to_cct(dwg), s("midtones"))
    dwg = lut_node("contrast", cct_to_dwg(cct), s("contrast_curve"))
    dwg = lut_node("shadows", dwg, s("shadows"))
    dwg = lut_node("satfix", dwg, s("satfix"))

    if p["contrast"] != 1.0 or p["saturation"] != 1.0 or p["exposure"] != 0.0:
        dwg = cct_to_dwg(extras(dwg_to_cct(dwg), p["contrast"], p["pivot"], p["saturation"], p["exposure"]))
    out = dwg if p["space"] == 0 else dwg_to_cct(dwg)
    return src + s("blend") * (out - src)


# ---------------------------------------------------------------------------
#  Tables for the DCTL
# ---------------------------------------------------------------------------
CURVE_N = 1025          # samples of the Diffusion curve over code 0 .. 1


def curve_table():
    return diffusion_curve(np.linspace(0.0, 1.0, CURVE_N))
