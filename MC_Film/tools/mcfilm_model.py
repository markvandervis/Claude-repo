"""MC Film - film model, reference implementation and DCTL table builder.

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

This module does two jobs:

  1. build_tables()   reads film / print stock profiles, reduces them to the
                      compact tables the DCTL needs (10 nm spectra, 64-point
                      characteristic curves, 3x3 exposure matrices, print
                      balance offsets) and writes them as C source.
  2. render_pixel()   the reference implementation of the DCTL's colour maths,
                      line for line, used by the tests.

STOCK DATA
  The stock characteristics (spectral sensitivities, dye densities, base
  densities, characteristic curves) come from the spektrafilm profiles by
  Andrea Volpato, https://github.com/andreavolpato/spektrafilm, licensed
  CC BY-SA 4.0.  This module only READS them; the tables it writes are a
  modified (resampled and reduced) derivative and stay CC BY-SA 4.0 with the
  attribution written into their header.  No spektrafilm code is used: the
  film model below is an independent implementation.

  Other spectral data (CIE 1931 observer, illuminants, the Mallett & Yuksel
  2019 sRGB basis, the Kinoton 75P projector lamp) comes from colour-science
  (BSD-3-Clause).

THE MODEL (all our own design)
  scene linear Rec.709
    -> soft gamut compression into Rec.709
    -> film layer exposure  raw = M_neg @ rgb           (Mallett basis x
                                                         reference light x
                                                         layer sensitivity,
                                                         exact for this basis)
    -> develop              D_k = g * curve_k(log10 raw_k + exposure)
    -> negative spectrum    T(l) = 10^-(base(l) + sum_k D_k dye_k(l))
    -> printing             logH_j = log10(sum_l lamp(l) T(l) S_j(l))
                                     + balance_j + 0.025 * printer points_j
    -> print develop        P_j = curve_j(logH_j)
    -> projection           T_p(l) = 10^-(base_p(l) + sum_j P_j dye_j(l))
                            XYZ = sum_l light(l) T_p(l) cmf(l) / Y_white
    -> chromatic adaptation to D65, display encoding.
  Balance offsets are solved so that a scene 18% grey prints as a neutral
  grey at the laboratory aim density (1.0) under the viewing light.
"""

from __future__ import annotations

import glob
import json
import math
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
#  stock selection (order = combo box order in the DCTL)
# ---------------------------------------------------------------------------
NEGATIVES = [
    ("NEG_V3_50D",    "Kodak Vision3 50D",   "kodak_vision3_50d"),
    ("NEG_V3_250D",   "Kodak Vision3 250D",  "kodak_vision3_250d"),
    ("NEG_V3_200T",   "Kodak Vision3 200T",  "kodak_vision3_200t"),
    ("NEG_V3_500T",   "Kodak Vision3 500T",  "kodak_vision3_500t"),
    ("NEG_PORTRA160", "Kodak Portra 160",    "kodak_portra_160"),
    ("NEG_PORTRA400", "Kodak Portra 400",    "kodak_portra_400"),
    ("NEG_PORTRA800", "Kodak Portra 800",    "kodak_portra_800"),
    ("NEG_EKTAR100",  "Kodak Ektar 100",     "kodak_ektar_100"),
    ("NEG_GOLD200",   "Kodak Gold 200",      "kodak_gold_200"),
    ("NEG_UMAX400",   "Kodak Ultramax 400",  "kodak_ultramax_400"),
    ("NEG_PRO400H",   "Fujifilm Pro 400H",   "fujifilm_pro_400h"),
    ("NEG_C200",      "Fujifilm C200",       "fujifilm_c200"),
    ("NEG_XTRA400",   "Fujifilm Xtra 400",   "fujifilm_xtra_400"),
]
PRINTS = [
    ("PRT_2383",      "Kodak 2383",                 "kodak_2383"),
    ("PRT_2393",      "Kodak 2393",                 "kodak_2393"),
    ("PRT_PENDURA",   "Kodak Portra Endura",        "kodak_portra_endura"),
    ("PRT_EPREMIER",  "Kodak Endura Premier",       "kodak_endura_premier"),
    ("PRT_SUPRA",     "Kodak Supra Endura",         "kodak_supra_endura"),
    ("PRT_ULTRA",     "Kodak Ultra Endura",         "kodak_ultra_endura"),
    ("PRT_EDGE",      "Kodak Ektacolor Edge",       "kodak_ektacolor_edge"),
    ("PRT_CA2",       "Fujifilm Crystal Archive",   "fujifilm_crystal_archive_typeii"),
]
OUTPUTS = [
    ("OUT_709",     "Rec709 Gamma 2.4"),
    ("OUT_SRGB",    "sRGB"),
    ("OUT_P3",      "P3 D65 Gamma 2.6"),
    ("OUT_2020",    "Rec2020 Gamma 2.4"),
    ("OUT_DWG",     "DaVinci WG Intermediate"),
    ("OUT_CINEON",  "Negative Cineon Log"),
]
INPUTS = [
    ("IN_DWG",      "DaVinci WG Intermediate"),
    ("IN_ACESCCT",  "ACES AP1 ACEScct"),
    ("IN_LINEAR",   "Scene Linear Rec709"),
    ("IN_709",      "Rec709 Gamma 2.4"),
    ("IN_CINEON",   "Negative Cineon Log"),
]

# ---------------------------------------------------------------------------
#  model constants (shared with the DCTL)
# ---------------------------------------------------------------------------
WL = np.arange(380.0, 781.0, 10.0)          # 41 bands
NWL = len(WL)
CURVE_N = 64                                 # samples per characteristic curve
NEG_LOGE_MIN, NEG_LOGE_MAX = -3.0, 4.0
MIDGRAY = 0.184
PRINT_AIM_DENSITY = 1.0                      # laboratory aim density for 18 % grey
PRINTER_POINT = 0.025                        # log exposure per printer point
LOG10_2 = math.log10(2.0)
ENLARGER_CCT = 3200.0                        # printer lamp colour temperature
LAMP_IR_CUT_NM = 700.0                       # heat-filter roll-off of the lamp
GAMUT_THRESHOLD = 0.8                        # input gamut compression
GAMUT_LIMIT = 1.2
GAMUT_POWER = 1.2

REC709_TO_XYZ = np.array([[0.4123908, 0.3575843, 0.1804808],
                          [0.2126390, 0.7151687, 0.0721923],
                          [0.0193308, 0.1191948, 0.9505322]])
XYZ_TO = {
    "OUT_709":  np.linalg.inv(REC709_TO_XYZ),
    "OUT_DWG":  np.linalg.inv(REC709_TO_XYZ),
    "OUT_SRGB": np.linalg.inv(REC709_TO_XYZ),
    "OUT_P3":   np.array([[2.4934969, -0.9313836, -0.4027108],
                          [-0.8294890, 1.7626641, 0.0236247],
                          [0.0358458, -0.0761724, 0.9568845]]),
    "OUT_2020": np.array([[1.7166512, -0.3556708, -0.2533663],
                          [-0.6666844, 1.6164812, 0.0157685],
                          [0.0176399, -0.0427706, 0.9421031]]),
}
# input primaries -> linear Rec.709 (rows normalised to 1, as in MC HSL Editor)
DWG_TO_REC709 = np.array([[1.89871504, -0.79180471, -0.10691033],
                          [-0.16894835, 1.48839859, -0.31945024],
                          [-0.12152602, -0.31546761, 1.43699363]])
REC709_TO_DWG = np.array([[0.56273797, 0.32348330, 0.11377874],
                          [0.07775428, 0.74978114, 0.17246458],
                          [0.06466018, 0.19195861, 0.74338121]])
AP1_TO_REC709 = np.array([[1.70505099, -0.62179212, -0.08325887],
                          [-0.13025642, 1.14080474, -0.01054832],
                          [-0.02400336, -0.12896898, 1.15297233]])


# ---------------------------------------------------------------------------
#  spectral helpers (colour-science, BSD)
# ---------------------------------------------------------------------------
def _colour():
    import colour
    return colour


def _align(sd):
    colour = _colour()
    return np.array(sd.copy().align(colour.SpectralShape(380, 780, 10)).values, dtype=float)


def cmfs():
    colour = _colour()
    m = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy()
    m = m.align(colour.SpectralShape(380, 780, 10))
    return np.array(m.values, dtype=float)


def blackbody(cct):
    c2 = 1.4388e-2
    lam = WL * 1e-9
    return 1.0 / (lam ** 5 * (np.exp(c2 / (lam * cct)) - 1.0))


def illuminant(name):
    colour = _colour()
    if name == "T":
        s = _align(colour.SDS_ILLUMINANTS["A"])
    elif name == "K75P":
        s = _align(colour.SDS_LIGHT_SOURCES["Kinoton 75P"])
    elif name == "TH-KG3":
        s = enlarger_lamp()
    else:
        s = _align(colour.SDS_ILLUMINANTS[name])
    return s / s.mean()


def enlarger_lamp():
    """Our printer lamp: a 3200 K tungsten source behind a heat filter,
    modelled as a smooth logistic roll-off above 700 nm."""
    s = blackbody(ENLARGER_CCT) / (1.0 + np.exp((WL - LAMP_IR_CUT_NM) / 15.0))
    return s / s.mean()


def mallett_basis():
    colour = _colour()
    b = colour.recovery.MSDS_BASIS_FUNCTIONS_sRGB_MALLETT2019
    b = b.copy().align(colour.SpectralShape(380, 780, 10))
    return np.array(b.values, dtype=float)                   # (41, 3)


# ---------------------------------------------------------------------------
#  profiles -> compact stock tables
# ---------------------------------------------------------------------------
def _to10(arr):
    """5 nm (81) -> 10 nm (41) with a [1/4, 1/2, 1/4] kernel, NaN-aware."""
    a = np.array(arr, dtype=float)
    out = []
    for i in range(0, 81, 2):
        idx = [j for j in (i - 1, i, i + 1) if 0 <= j < 81]
        w = np.array([0.5 if j == i else 0.25 for j in idx])
        v = a[idx]
        ok = ~np.isnan(v)
        if a.ndim == 1:
            out.append(np.nan if not ok.any() else float((v[ok] * w[ok]).sum() / w[ok].sum()))
        else:
            col = []
            for c in range(a.shape[1]):
                okc = ok[:, c]
                col.append(np.nan if not okc.any() else float((v[okc, c] * w[okc]).sum() / w[okc].sum()))
            out.append(col)
    return np.array(out)


def _fill_edges(a):
    """Replace NaN at the spectrum ends by the nearest measured value.  Used for
    dye and base densities: a dye does not stop absorbing where the datasheet
    stops measuring, and treating unmeasured bands as clear lets unmodulated
    light through to the next stage (it flattens the blue print layer)."""
    a = np.array(a, dtype=float)
    if a.ndim == 1:
        ok = np.where(~np.isnan(a))[0]
        a[:ok[0]] = a[ok[0]]
        a[ok[-1] + 1:] = a[ok[-1]]
        a[np.isnan(a)] = np.interp(np.where(np.isnan(a))[0], ok, a[ok])
        return a
    return np.stack([_fill_edges(a[:, c]) for c in range(a.shape[1])], axis=1)


def _curve_table(log_e, curves, lo, hi):
    """Resample characteristic curves onto CURVE_N uniform samples on [lo, hi],
    forcing them to be non-decreasing (the data is, up to measurement noise)."""
    x = np.linspace(lo, hi, CURVE_N)
    le = np.array(log_e, dtype=float)
    c = np.array(curves, dtype=float)
    out = np.zeros((CURVE_N, 3))
    for k in range(3):
        ok = ~np.isnan(c[:, k])
        out[:, k] = np.interp(x, le[ok], c[ok, k])
        out[:, k] = np.maximum.accumulate(out[:, k])
    return out


def load_profile(directory, key):
    with open(os.path.join(directory, key + ".json")) as f:
        return json.load(f)


def negative_tables(prof):
    d, info = prof["data"], prof["info"]
    sens = np.nan_to_num(10.0 ** _to10(d["log_sensitivity"]))              # (41,3)
    light = illuminant(info["reference_illuminant"])
    basis = mallett_basis()
    # raw_k = sum_l basis_c(l) light(l) sens_k(l) rgb_c  ->  M[k, c]
    m = np.einsum("lc,l,lk->kc", basis, light, sens)
    norm = (light * MIDGRAY) @ sens[:, 1]
    m = m / norm
    return {
        "matrix": m,
        "loge_mid": np.log10(m @ np.array([MIDGRAY] * 3)),
        "curves": _curve_table(d["log_exposure"], d["density_curves"], NEG_LOGE_MIN, NEG_LOGE_MAX),
        "dyes": _fill_edges(_to10(d["channel_density"])),
        "base": _fill_edges(_to10(d["base_density"])),
    }


def print_tables(prof):
    d, info = prof["data"], prof["info"]
    le = np.array(d["log_exposure"], dtype=float)
    lo, hi = float(le.min()), float(le.max())
    view = illuminant(info["viewing_illuminant"])
    xyz_w = view @ cmfs()
    xyz_w = xyz_w / xyz_w[1]
    colour = _colour()
    cat = colour.adaptation.matrix_chromatic_adaptation_VonKries(
        xyz_w, colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]),
        transform="CAT02")
    return {
        "sens": np.nan_to_num(10.0 ** _to10(d["log_sensitivity"])),
        "curves": _curve_table(le, d["density_curves"], lo, hi),
        "loge_min": lo, "loge_max": hi,
        "dyes": _fill_edges(_to10(d["channel_density"])),
        "base": _fill_edges(_to10(d["base_density"])),
        "view": view,
        "cat": cat,
    }


# ---------------------------------------------------------------------------
#  the model (mirrors the DCTL)
# ---------------------------------------------------------------------------
def curve_eval(table, x, lo, hi):
    """Monotone cubic Hermite (Fritsch-Carlson tangents) on a uniform grid."""
    n = table.shape[0]
    dx = (hi - lo) / (n - 1)
    t = (x - lo) / dx
    if t <= 0.0:
        return float(table[0])
    if t >= n - 1:
        return float(table[n - 1])
    i = int(math.floor(t))
    f = t - i
    y0 = table[max(i - 1, 0)]
    y1 = table[i]
    y2 = table[i + 1]
    y3 = table[min(i + 2, n - 1)]
    s0, s1, s2 = y1 - y0, y2 - y1, y3 - y2

    def tangent(a, b):
        return 0.0 if a * b <= 0.0 else 2.0 * a * b / (a + b)

    m1 = tangent(s0, s1) if i > 0 else s1
    m2 = tangent(s1, s2) if i + 2 < n else s1
    f2, f3 = f * f, f * f * f
    return float((2 * f3 - 3 * f2 + 1) * y1 + (f3 - 2 * f2 + f) * m1 +
                 (-2 * f3 + 3 * f2) * y2 + (f3 - f2) * m2)


def decode_input(rgb, encoding):
    def di_decode(y):
        return 2.0 ** (min(y, 5.0) / 0.07329248 - 7.0) - 0.0075 if y > 0.02740668 else y / 10.44426855

    def cct_decode(y):
        return 2.0 ** (min(y, 4.0) * 17.52 - 9.72) if y > 0.155251141552511 else (y - 0.0729055341958355) / 10.5402377416545

    if encoding == "IN_DWG":
        return DWG_TO_REC709 @ np.array([di_decode(v) for v in rgb])
    if encoding == "IN_ACESCCT":
        return AP1_TO_REC709 @ np.array([cct_decode(v) for v in rgb])
    if encoding == "IN_709":
        return np.array([max(v, 0.0) ** 2.4 for v in rgb])
    return np.array(rgb, dtype=float)


def gamut_compress(rgb):
    """Soft compression of out-of-Rec.709 colours (negative channels) towards
    the achromatic axis.  Distances below GAMUT_THRESHOLD are untouched; the
    distance GAMUT_LIMIT is mapped onto the gamut boundary."""
    mx = max(rgb)
    if mx <= 0.0:
        return np.maximum(rgb, 0.0)
    thr, lim, p = GAMUT_THRESHOLD, GAMUT_LIMIT, GAMUT_POWER
    s = (lim - thr) / (((1.0 - thr) / (lim - thr)) ** -p - 1.0) ** (1.0 / p)
    out = []
    for c in rgb:
        d = (mx - c) / mx
        if d > thr:
            x = (d - thr) / s
            d = thr + s * x / (1.0 + x ** p) ** (1.0 / p)
        out.append(mx - d * mx)
    return np.array(out)


def negative_density(rgb_lin, neg, exposure_stops, gamma, film_sat=1.0):
    """Development gamma acts on log exposure around the 18 % grey exposure of
    each layer, so the stock's own toe and shoulder still bound the result and
    18 % grey keeps its density (the print stays timed).

    Film saturation scales how far the three layer exposures (relative to
    their 18 % grey exposures) spread around their mean: a grey has no spread
    and is untouched, 0 makes every colour a grey of the same exposure."""
    raw = neg["matrix"] @ rgb_lin
    e = np.array([math.log10(max(raw[k], 1e-10)) + exposure_stops * LOG10_2 - neg["loge_mid"][k]
                  for k in range(3)])
    if film_sat != 1.0:
        mean = e.mean()
        e = mean + film_sat * (e - mean)
    return np.array([curve_eval(neg["curves"][:, k], neg["loge_mid"][k] + gamma * e[k], NEG_LOGE_MIN, NEG_LOGE_MAX)
                     for k in range(3)])


def print_log_exposure(dens, neg, prt, lamp):
    t = 10.0 ** -(neg["base"] + neg["dyes"] @ dens)
    h = (lamp * t) @ prt["sens"]
    return np.log10(np.maximum(h, 1e-10))


def print_xyz(pd, prt, cmf):
    t = 10.0 ** -(prt["base"] + prt["dyes"] @ pd)
    w = prt["view"]
    return ((w * t) @ cmf) / (w @ cmf[:, 1])


def print_density(log_h, prt, contrast=1.0, pivot=None):
    """Print development; contrast acts on log exposure around `pivot` (the
    balanced 18 % grey exposure), like the negative's development gamma."""
    if pivot is not None:
        log_h = pivot + contrast * (np.asarray(log_h) - pivot)
    return np.array([curve_eval(prt["curves"][:, j], log_h[j], prt["loge_min"], prt["loge_max"])
                     for j in range(3)])


def solve_balance(neg, prt, lamp, cmf):
    """Per-channel log-exposure offsets that print a scene 18 % grey as a
    neutral (under the viewing light) at the laboratory aim density."""
    d_mid = negative_density(np.array([MIDGRAY] * 3), neg, 0.0, 1.0)
    h_mid = print_log_exposure(d_mid, neg, prt, lamp)
    w = prt["view"] @ cmf
    w = w / w[1]
    target = w * 10.0 ** -PRINT_AIM_DENSITY

    def residual(off):
        xyz = print_xyz(print_density(h_mid + off, prt, 1.0), prt, cmf)
        return np.log10(np.maximum(xyz, 1e-12)) - np.log10(target)

    off = -h_mid + np.array([curve_inverse(prt, j, PRINT_AIM_DENSITY) for j in range(3)])
    for _ in range(60):                      # damped Gauss-Newton
        r = residual(off)
        if np.max(np.abs(r)) < 1e-9:
            break
        jac = np.zeros((3, 3))
        for j in range(3):
            e = np.zeros(3)
            e[j] = 1e-5
            jac[:, j] = (residual(off + e) - r) / 1e-5
        off = off - 0.8 * np.linalg.solve(jac, r)
    return off


def curve_inverse(prt, j, density):
    x = np.linspace(prt["loge_min"], prt["loge_max"], CURVE_N)
    return float(np.interp(density, prt["curves"][:, j], x))


# ---------------------------------------------------------------------------
#  table build
# ---------------------------------------------------------------------------
def build_tables(profile_dir):
    lamp = enlarger_lamp()
    cmf = cmfs()
    negs = [negative_tables(load_profile(profile_dir, k)) for _, _, k in NEGATIVES]
    prts = [print_tables(load_profile(profile_dir, k)) for _, _, k in PRINTS]
    balance = np.array([[solve_balance(n, p, lamp, cmf) for p in prts] for n in negs])
    pivot = np.array([[print_log_exposure(negative_density(np.array([MIDGRAY] * 3), n, 0.0, 1.0), n, p, lamp)
                       + balance[i][j] for j, p in enumerate(prts)] for i, n in enumerate(negs)])
    for n in negs:
        n["d_mid"] = negative_density(np.array([MIDGRAY] * 3), n, 0.0, 1.0)
    p_mid = np.array([[print_density(pivot[i][j], p) for j, p in enumerate(prts)] for i in range(len(negs))])
    slope = np.array([[(print_density(pivot[i][j] + 1e-3, p) - print_density(pivot[i][j] - 1e-3, p)) / 2e-3
                       for j, p in enumerate(prts)] for i in range(len(negs))])
    vslope = np.array([[print_visual_slope(pivot[i][j], p, cmf) for j, p in enumerate(prts)]
                       for i in range(len(negs))])
    dslope = np.array([[float(np.mean((print_density(pivot[i][j] + 1e-3, p) - print_density(pivot[i][j] - 1e-3, p))
                                      / 2e-3)) for j, p in enumerate(prts)] for i in range(len(negs))])
    return {"negs": negs, "prints": prts, "balance": balance, "pivot": pivot, "print_d_mid": p_mid,
            "print_vslope_mid": vslope, "print_dslope_mid": dslope, "lamp": lamp, "cmf": cmf}


def print_bleach_retime(d_mid, vslope, dslope, k, e, contrast):
    """Neutral print log-exposure reduction that keeps 18 % grey's visual
    density when bleach-bypass silver k * mean(D)^e is added to the print.
    Less exposure means less dye and therefore also less silver, so solve
        k (m - c dslope x)^e = c vslope x
    for x with three Newton steps (m = mean dye density at 18 % grey)."""
    if k <= 0.0:
        return 0.0
    m = float(np.mean(d_mid))
    a, b = contrast * dslope, contrast * vslope
    x = 0.0
    for _ in range(3):
        u = max(m - a * x, 1e-6)
        f = k * u ** e - b * x
        df = -k * e * a * u ** (e - 1.0) - b
        x = x - f / df
    return x


def print_visual_slope(pivot, prt, cmf, delta=1e-3):
    """Visual (Y) density gained per unit of neutral print log exposure at the
    balanced 18 % grey: how much less exposure removes a given flat density."""
    def vis(h):
        y = print_xyz(print_density(h, prt), prt, cmf)[1]
        return -math.log10(y)
    return (vis(pivot + delta) - vis(pivot - delta)) / (2 * delta)


def save_tables(tables, path):
    def conv(o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        return o
    with open(path, "w") as f:
        json.dump(conv(tables), f)


def load_tables(path):
    with open(path) as f:
        t = json.load(f)
    for group in ("negs", "prints"):
        t[group] = [{k: (np.array(v) if isinstance(v, list) else v) for k, v in s.items()} for s in t[group]]
    for k in ("balance", "pivot", "print_d_mid", "print_vslope_mid", "print_dslope_mid", "lamp", "cmf"):
        t[k] = np.array(t[k])
    return t


# ---------------------------------------------------------------------------
#  full reference render (mirrors transform() in the DCTL)
# ---------------------------------------------------------------------------
def di_encode(x):
    return (math.log2(x + 0.0075) + 7.0) * 0.07329248 if x > 0.00262409 else x * 10.44426855


def encode_output(rgb, output):
    if output == "OUT_DWG":
        # display-linear Rec.709 carried into DaVinci WG / Intermediate, no
        # clipping: a CST DWG/DI -> Rec.709 Gamma 2.4 with tone mapping and
        # gamut mapping off gives back the Rec709 Gamma 2.4 output exactly
        return np.array([di_encode(v) for v in REC709_TO_DWG @ rgb])
    rgb = np.maximum(rgb, 0.0)
    if output == "OUT_SRGB":
        return np.array([12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in rgb])
    g = 2.6 if output == "OUT_P3" else 2.4
    return np.array([max(v, 0.0) ** (1.0 / g) for v in rgb])


def prepare(tables):
    """Add the pre-multiplied tables the DCTL uses (lamp x print sensitivity,
    viewing light x CMFs scaled so the clear print has Y = 1)."""
    lamp, cmf = tables["lamp"], tables["cmf"]
    for p in tables["prints"]:
        p["lampsens"] = lamp[:, None] * p["sens"]
        white_y = (p["view"] * 10.0 ** -p["base"]) @ cmf[:, 1]
        p["viewcmf"] = p["view"][:, None] * cmf / white_y
    return tables


# Cineon negative encoding: base at code 95 of 1023, 0.002 density per code.
# Carries the developed DYE densities only; negative-stage bleach bypass
# silver is applied by the node that prints, from these densities.
CINEON_BLACK = 95.0 / 1023.0
CINEON_DENSITY_PER_CODE = 2.046


# Bleach bypass: retained metallic silver is a spectrally flat density that
# follows the dye density of the layer stack: silver = k * mean(D)^e.
BLEACH_MODES = {"off": (0.0, 1.0), "authentic": (0.5, 1.0), "grunge": (0.75, 1.6)}


def silver_density(dens, k, e):
    return 0.0 if k <= 0.0 else k * max(float(np.mean(dens)), 0.0) ** e


def render_pixel(rgb, tables, neg_i=1, prt_i=0, encoding="IN_DWG", output="OUT_709",
                 exposure=0.0, push=0.0, printer=(0.0, 0.0, 0.0), print_exposure=0.0,
                 neg_contrast=1.0, print_contrast=1.0, gamut=True, film_sat=1.0,
                 bleach="off", bleach_stage="print", bleach_strength=0.7, silver_contrast=1.0,
                 preserve_mid=True):
    """Mirror of the DCTL's transform()."""
    if "lampsens" not in tables["prints"][0]:
        prepare(tables)
    neg = tables["negs"][neg_i]
    prt = tables["prints"][prt_i]
    kb, eb = BLEACH_MODES[bleach]
    kb *= bleach_strength
    eb *= silver_contrast
    k_neg = kb if bleach_stage == "negative" else 0.0
    k_prt = kb if bleach_stage == "print" else 0.0

    # --- negative stage: scene -> developed dye densities ------------------
    if encoding == "IN_CINEON":
        dens = (np.asarray(rgb, dtype=float) - CINEON_BLACK) * CINEON_DENSITY_PER_CODE
    else:
        lin = decode_input(rgb, encoding)
        if gamut:
            lin = gamut_compress(lin)
        lin = np.maximum(lin, 0.0)
        dens = negative_density(lin, neg, exposure, neg_contrast * push_gamma(push), film_sat)
    if output == "OUT_CINEON":
        return CINEON_BLACK + dens / CINEON_DENSITY_PER_CODE

    # --- print stage: dye densities -> projected print ----------------------
    s_neg = silver_density(dens, k_neg, eb)
    t = 10.0 ** -(neg["base"] + neg["dyes"] @ dens + s_neg)
    log_h = np.log10(np.maximum(t @ prt["lampsens"], 1e-10))
    log_h = log_h + tables["balance"][neg_i][prt_i] + PRINTER_POINT * (np.array(printer) + print_exposure)
    pivot = tables["pivot"][neg_i][prt_i]
    if preserve_mid:
        # flat silver on the negative removes the same log exposure from all
        # three print layers: re-time by exactly that amount
        log_h = log_h + silver_density(neg["d_mid"], k_neg, eb)
        # silver on the print darkens 18 % grey: give the print that much
        # less exposure, measured in visual density
        log_h = log_h - print_bleach_retime(tables["print_d_mid"][neg_i][prt_i],
                                            tables["print_vslope_mid"][neg_i][prt_i],
                                            tables["print_dslope_mid"][neg_i][prt_i], k_prt, eb, print_contrast)
    pd = print_density(log_h, prt, print_contrast, pivot)
    s_prt = silver_density(pd, k_prt, eb)
    tp = 10.0 ** -(prt["base"] + prt["dyes"] @ pd + s_prt)
    xyz = prt["cat"] @ (tp @ prt["viewcmf"])
    return encode_output(XYZ_TO[output] @ xyz, output)


# push / pull, per stop of push: development gamma (on log exposure around
# 18 % grey) and effective speed (stops).  Fitted to the measured Portra 800
# push 1 / push 2 curves by calibrate_push().
PUSH_A = 0.245
PUSH_B = -0.045


def push_gamma(push):
    """Development gamma for `push` stops: 1 + a p + b p^2 for push (fits the
    measured x1.20 at push 1 and x1.31 at push 2), its reciprocal for pull.
    C1 at 0 and increasing over the slider range (-2 .. +2.5)."""
    q = abs(push)
    g = 1.0 + PUSH_A * q + PUSH_B * q * q
    return g if push >= 0.0 else 1.0 / g


def calibrate_push(profile_dir):
    """Fit pushed(x) ~ base(mid + g (x + s - mid)) for each push level."""
    base = load_profile(profile_dir, "kodak_portra_800")["data"]
    le = np.array(base["log_exposure"])
    src = np.array(base["density_curves"], dtype=float)
    mid = 0.0                                   # 18 % grey exposes at log E = 0 (green)
    res = []
    for p, key in ((1, "kodak_portra_800_push1"), (2, "kodak_portra_800_push2")):
        tgt = np.array(load_profile(profile_dir, key)["data"]["density_curves"], dtype=float)
        best = None
        for g in np.linspace(0.9, 1.6, 71):
            for sh in np.linspace(-0.3, 0.6, 91):
                err = 0.0
                for k in range(3):
                    x = mid + g * (le + sh - mid)
                    model = np.interp(x, le, src[:, k])
                    msk = (le > -2.0) & (le < 1.5) & ~np.isnan(tgt[:, k])
                    err += np.mean((model[msk] - tgt[msk, k]) ** 2)
                if best is None or err < best[0]:
                    best = (err, g, sh)
        res.append((p, best[1], best[2] / LOG10_2))
    return res
