#!/usr/bin/env python3
"""Test suite for MC Pro Split.

MarkCaptures MC Pro Split - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Compiles the real generated DCTL (C++11 and C99, warnings as errors) and
checks it against tools/mc_prosplit.py: identity at defaults, DCTL ==
reference in every encoding, grey ramps never reverse, and every control
acts in the right direction.

Run:  python3 tests/test_prosplit.py
"""

import math
import os
import random
import re
import sys

import numpy as np

import test_film_core as t
from test_film_core import check, section, f32

import build_dctl  # noqa: E402
import mc_prosplit as ps  # noqa: E402

EXE = os.path.join(t.HERE, "mcp_prosplit")
ENC = {e: i for i, (e, _) in enumerate(ps.ENCODINGS)}
ZVAR = ("Lo", "LoMid", "Mid", "HiMid", "Hi")          # zone index 0 .. 4
UI = dict(blend="uiBlend", pivot="uiPivot", neutral="uiNeutral", clean_blacks="uiCleanBlacks",
          clean_whites="uiCleanWhites", sat_mask="uiSatMask")


DI_PIV, DI_STOP, _ = ps.tf_constants("TF_DI", 0.0)
K = ps.SCALE * DI_STOP          # code-value offset of a zone slider at 100 (tests use +-1 = +-100)


def zone_ui(zones):
    return {"ui%s%s" % (ZVAR[i], ch): 100.0 * float(zones[i][k]) for i in range(5) for k, ch in enumerate("RGB")}


def run(px, zones=None, **kw):
    ui = {UI.get(k, k): v for k, v in kw.items()}
    if zones is not None:
        ui.update(zone_ui(zones))
    return t.run(px, exe=EXE, **ui)


def ref(px, enc="TF_DI", zones=None, **kw):
    p = dict(kw)
    if zones is not None:
        p["zones"] = 100.0 * np.array(zones, dtype=float)
    return [ps.pixel(c, enc, **p) for c in px]


def Z(**zones):
    z = np.zeros((5, 3))
    for name, v in zones.items():
        z[ZVAR.index(name)] = v
    return z


def grey(stops):
    return [(f32(ps.di_encode(ps.MIDGRAY * 2 ** s)),) * 3 for s in stops]


def col(*lin):
    return tuple(f32(ps.di_encode(v)) for v in ps.REC709_TO_DWG @ np.array(lin))


def maxdiff(a, b):
    return max(abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb))


def chroma(c):
    return float(np.linalg.norm(np.array(c) - np.mean(c)))


def test_static():
    section("1. static checks")
    src = open(build_dctl.SPLIT_OUTPUT, encoding="utf-8").read()
    lines = src.split("\n")
    banner = ["// MarkCaptures MC Pro Split", "// © 2026 Mark van der Vis / MarkCaptures", "// www.markcaptures.com"]
    check(lines[:3] == banner and [l for l in lines if l.strip()][-3:] == banner, "banner at top and bottom")
    entry = [l for l in lines if "float3 transform(" in l]
    check(len(entry) == 1 and entry[0] == "__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, "
          "float p_R, float p_G, float p_B)", "transform() on one line")
    params = re.findall(r"^DEFINE_UI_PARAMS\((\w+),", src, re.M)
    tips = re.findall(r"^DEFINE_UI_TOOLTIP\((\w+),", src, re.M)
    check(sorted(params) == sorted(tips), "every control has one tooltip")
    labels = re.findall(r"^DEFINE_UI_PARAMS\(\w+, ([^,]+), DCTLUI_SLIDER", src, re.M)
    zl = ["%s %s" % (z, c) for z in ("Hi", "Hi-Mid", "Mid", "Lo-Mid", "Lo") for c in ("Red", "Green", "Blue")]
    check(labels == zl + ["Blend", "Pivot", "Neutral Pivot", "Clean Blacks", "Clean Whites", "Sat Mask"],
          "sliders: five zones x RGB from Hi to Lo, then Blend, Pivot, Neutral Pivot, Clean Blacks / Whites, Sat Mask")
    code = re.sub(r"//.*", "", src)
    intr = set(re.findall(r"\b(_[a-z][a-z0-9]*)\s*\(", code))
    check("_exp10f" not in code and intr <= {"_fmaxf", "_fminf", "_fabs", "_sqrtf", "_powf", "_exp2f", "_log2f",
                                             "_expf", "_saturatef", "_clampf", "_floor"},
          "only standard intrinsics, no _exp10f (%s)" % sorted(intr))
    check("@@" not in src and not re.search(r"\bdouble\b", code), "no template fields, no double precision")


def test_identity():
    section("2. identity")
    rng = random.Random(1)
    px = [tuple(f32(rng.uniform(-0.1, 1.2)) for _ in range(3)) for _ in range(200)]
    for e, i in ENC.items():
        check(run(px, uiInput=i) == px, "%s: default settings return the input bit exact" % e)
    check(run(px, Z(Mid=(1, -1, 0.5)), uiBypass=1) == px, "Bypass is bit exact")
    check(run(px, Z(Mid=(1, -1, 0.5)), blend=0) == px, "Blend 0 is bit exact")
    check(run(px, pivot=1.3, neutral=50, clean_blacks=100, clean_whites=0, sat_mask=80) == px,
          "with all zones at 0 the other sliders change nothing (bit exact)")


def random_zones(rng):
    return np.array([[rng.choice([0.0, rng.uniform(-1, 1)]) for _ in range(3)] for _ in range(5)])


def test_cross():
    section("3. DCTL == reference")
    rng = random.Random(2)
    for e, i in ENC.items():
        if e == "TF_LINEAR":
            px = [tuple(f32(rng.uniform(0.0, 2.0) * rng.choice([0.05, 1.0])) for _ in range(3)) for _ in range(60)]
        else:
            px = [tuple(f32(rng.uniform(0.0, 0.9)) for _ in range(3)) for _ in range(60)]
        w = 0.0
        for _ in range(12):
            zones = random_zones(rng)
            p = dict(blend=rng.uniform(0, 100), pivot=rng.uniform(-3, 3), neutral=rng.choice([0.0, rng.uniform(0, 100)]),
                     clean_blacks=rng.uniform(0, 100), clean_whites=rng.uniform(0, 100),
                     sat_mask=rng.choice([0.0, rng.uniform(0, 100)]))
            w = max(w, maxdiff(run(px, zones, uiInput=i, **p), ref(px, e, zones, **p)))
        check(w < 2e-5 if e != "TF_LINEAR" else w < 5e-4, "%s: max |DCTL - reference| = %.1e" % (e, w))


def test_ramps():
    section("4. grey ramps never reverse")
    ramp = grey(np.linspace(-12, 8, 1001))
    rng = random.Random(3)

    def back(zones, **p):
        return -np.diff(np.array(run(ramp, zones, **p)), axis=0).min()
    cleans = (dict(clean_blacks=0, clean_whites=0), dict(clean_blacks=100, clean_whites=100),
              dict(clean_blacks=40, clean_whites=40), dict(pivot=3, clean_blacks=100), dict(pivot=-3, clean_whites=100))
    worst = 0.0
    for i in range(5):
        for v in ((1, 1, 1), (-1, -1, -1), (1, -1, 0), (-1, 1, -1)):
            z = np.zeros((5, 3)); z[i] = v
            for p in cleans:
                worst = max(worst, back(z, **p))
    check(worst < 1e-6, "any single zone at +-100, any Clean setting (worst %.1e)" % worst)
    worst = 0.0
    for _ in range(30):
        z = np.array([[rng.uniform(-0.5, 0.5) for _ in range(3)] for _ in range(5)])
        for p in cleans:
            worst = max(worst, back(z, **p))
    check(worst < 1e-6, "random zones within +-50, any Clean setting (worst %.1e)" % worst)
    alt = Z(Lo=(1, 1, 1), LoMid=(-1, -1, -1), Mid=(1, 1, 1), HiMid=(-1, -1, -1), Hi=(1, 1, 1))
    w = max(back(alt, **p) for p in cleans)
    check(w < 1e-6, "neighbouring zones at opposite +-100 (worst %.1e)" % w)


def test_controls():
    section("5. controls")
    centres = {"Lo": -4, "LoMid": -2, "Mid": 0, "HiMid": 2, "Hi": 4}

    def greyx(x):            # a grey x stops from the pivot on the DaVinci Intermediate log scale
        v = f32(DI_PIV + x * DI_STOP)
        return [(v, v, v)]
    cx = {n: ps.ZONE_CENTRE0 + ps.ZONE_STEP * i for i, n in enumerate(ZVAR)}
    for name in ZVAR:
        resp = {n: run(greyx(c), Z(**{name: (1, 0, 0)}), clean_blacks=0, clean_whites=0)[0][0] - greyx(c)[0][0]
                for n, c in cx.items()}
        check(max(resp, key=resp.get) == name and min(resp.values()) > 0.0,
              "%s Red +100: strongest at its own centre (%+.2f stops), reaching broadly into the others" %
              (name, cx[name]))
    # the reference curves: Lo Red -100, measured from screenshots at three Clean Blacks settings
    meas = {51.2: [(0.12, .0546), (0.20, .0618), (0.32, .0329), (0.44, .0133)],
            66.7: [(0.12, .0206), (0.20, .0339), (0.32, .0275), (0.44, .0132)],
            100.0: [(0.20, .0108), (0.32, .0118), (0.44, .0096)]}
    worst = 0.0
    for cb, pts in meas.items():
        for u, gap in pts:
            v = f32(u)
            o = run([(v, v, v)], Z(Lo=(-1, 0, 0)), clean_blacks=cb)[0]
            worst = max(worst, abs((v - o[0]) - gap))
    check(worst < 0.008, "Lo Red -100 matches the reference curves at Clean Blacks 51 / 67 / 100 (within %.4f)" % worst)
    ramp = grey(np.linspace(-6, 6, 25))
    same = run(ramp, Z(**{n: (0.5, -0.3, 0.2) for n in ZVAR}), clean_blacks=0, clean_whites=0)
    d = np.array(same) - np.array(ramp)
    check(np.abs(d - K * np.array([0.5, -0.3, 0.2])).max() < 2e-5,
          "the same setting on all five zones is one plain offset")
    full = np.array(run(grey((0,)), Z(Mid=(1, 0, 0)))[0]) - np.array(grey((0,))[0])
    half = np.array(run(grey((0,)), Z(Mid=(1, 0, 0)), blend=50)[0]) - np.array(grey((0,))[0])
    check(abs(half[0] - 0.5 * full[0]) < 2e-6, "Blend 50 gives half the toning")
    piv = run(grey((1.0,)), Z(Mid=(1, 0, 0)), pivot=1.0)[0][0] - grey((1.0,))[0][0]
    check(abs(piv - full[0]) < 2e-4, "Pivot +1 moves the zones up one stop")
    nm = np.array(run(grey((0,)), Z(Mid=(1, 0, -1)), neutral=100)[0]) - np.array(grey((0,))[0])
    check(np.abs(nm).max() < 1e-6, "Neutral Pivot 100 keeps the pivot grey neutral (Mid tint removed)")
    nb = np.array(run(grey((0,)), Z(Mid=(1, 1, 1)), neutral=100)[0]) - np.array(grey((0,))[0])
    check(nb.min() > 0.2 * K, "but Mid can still brighten the pivot")
    deep = grey((-10,)) + [(0.0, 0.0, 0.0)]
    check(maxdiff(run(deep, Z(Lo=(1, -1, 1)), clean_blacks=100), deep) < 2e-4 and
          maxdiff(run(deep, Z(Lo=(1, -1, 1)), clean_blacks=0), deep) > 0.02, "Clean Blacks 100 keeps black neutral")
    top = [(1.0, 1.0, 1.0)]
    check(maxdiff(run(top, Z(Hi=(1, -1, 1)), clean_whites=100), top) < 1e-6 and
          maxdiff(run(top, Z(Hi=(1, -1, 1)), clean_whites=0), top) > 0.02, "Clean Whites 100 keeps the top of the range neutral")
    sat = [col(0.30, 0.02, 0.02)]
    s0 = maxdiff(run(sat, Z(Mid=(0, 1, 1)), sat_mask=0), sat)
    s1 = maxdiff(run(sat, Z(Mid=(0, 1, 1)), sat_mask=100), sat)
    gm = grey((0,))
    check(s1 < 0.05 * s0 and maxdiff(run(gm, Z(Mid=(0, 1, 1)), sat_mask=100), gm) > 0.02,
          "Sat Mask 100 leaves a saturated colour alone but still tones grey")


def test_curves_extremes():
    section("6. Show Curves, extremes")
    rng = random.Random(4)
    pts = [(rng.randrange(1920), rng.randrange(1080), 0.4, 0.3, 0.2) for _ in range(3000)]
    zz = Z(Lo=(0, 0.5, 0.8), Hi=(0.8, 0.3, -0.5))
    off = run(pts)
    on = run(pts, zz, uiShowCurves=1)
    tone = run(pts, zz)
    line = [i for i, (a, b) in enumerate(zip(on, tone)) if a != b]
    for tf in ("TF_DI", "TF_SLOG3", "TF_LOGC3"):
        mid = ps.tf_encode(ps.MIDGRAY, tf)
        col_x = int(mid * 1920)
        o = run([(col_x, 500, 0.2, 0.2, 0.2), (col_x + 40, 500, 0.2, 0.2, 0.2)], uiShowCurves=1, uiInput=ENC[tf])
        check(o[0][0] > 0.9 and o[1][0] < 0.3, "%s: Show Curves draws the middle grey line at %.3f" % (tf, mid))
    ramp = run([(x, 1079, 0.5, 0.5, 0.5) for x in (100, 1800)], zz, uiShowRamp=1)
    check(ramp[0][0] < 0.1 and ramp[1][0] > 0.9 and run([(100, 0, 0.5, 0.5, 0.5)], zz, uiShowRamp=1)[0] != ramp[0],
          "Show Ramp puts a toned grey ramp along the bottom")
    sm = run([col(0.3, 0.02, 0.02), (f32(0.4), f32(0.4), f32(0.4))], uiShowSatMask=1, sat_mask=100)
    check(sm[0][1] < sm[0][0] and sm[0][1] < sm[0][2] and max(sm[1]) - min(sm[1]) < 1e-6,
          "Highlight Sat Mask paints the masked colours magenta and shows the rest in grey")
    check(5 < len(line) < 1500, "Show Curves draws thin lines over the frame (%d of 3000 random pixels)" % len(line))
    check(all(on[i] == tone[i] for i in range(len(pts)) if i not in line) and off[0] == (f32(0.4), f32(0.3), f32(0.2)),
          "elsewhere the picture is the toned image, unchanged")
    wild = [(0, 0, 0), (1e6, 1e6, 1e6), (-5, -5, -5), (50, -3, 0.2), (0.5, 0.5, -20), (1e-30, 0, 0)]
    ok = True
    for i in ENC.values():
        o = run(wild, Z(Lo=(1, -1, 1), Mid=(-1, 1, -1), Hi=(1, 1, -1)), uiInput=i, sat_mask=50, neutral=50)
        ok &= all(math.isfinite(v) for x in o for v in x)
    check(ok, "finite output for extreme inputs in every encoding")


def main():
    t.write_enums()
    with open(os.path.join(t.HERE, "mcf_enums.h"), "a") as f:
        f.write("enum { %s };\n" % ", ".join("%s = %d" % (e, i) for i, (e, _) in enumerate(ps.ENCODINGS)))
    t.build_one(build_dctl.SPLIT_OUTPUT, EXE)
    print("built tests/mcp_prosplit; the DCTL compiles clean as C++11 and C99")
    test_static()
    test_identity()
    test_cross()
    test_ramps()
    test_controls()
    test_curves_extremes()
    print("\n%d checks, %d failed" % (t._n, len(t._fail)))
    return 1 if t._fail else 0


if __name__ == "__main__":
    sys.exit(main())
