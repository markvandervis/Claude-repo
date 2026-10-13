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
UI = dict(amount="uiAmount", hue="uiHue", desat="uiDesat", balance="uiBalance", mid="uiMid", hold="uiHold",
          knee="uiKnee", black="uiBlack", cast="uiCast", cast_hue="uiCastHue", twist_s="uiTwistS",
          twist_h="uiTwistH", skin="uiSkin")


def run(px, **kw):
    ui = {UI.get(k, k): v for k, v in kw.items()}
    return t.run(px, exe=EXE, **ui)


def grey(stops):
    return [(f32(ps.di_encode(ps.MIDGRAY * 2 ** s)),) * 3 for s in stops]


def col(*lin):
    """a DWG / DI pixel from Rec.709 linear values"""
    return tuple(f32(ps.di_encode(v)) for v in ps.REC709_TO_DWG @ np.array(lin))


def maxdiff(a, b):
    return max(abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb))


def chroma(c):
    c = np.array(c) - np.mean(c)
    return float(np.linalg.norm(c))


def hue(c):
    c = np.array(c) - np.mean(c)
    return math.degrees(math.atan2(float(c @ ps.E2), float(c @ ps.E1)))


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
    check(labels == ["Crossover Amount", "Crossover Hue", "Desat Protect", "Crossover Balance", "Middle Grey",
                     "Midtone Hold", "Crossover Knee", "Black Neutral", "Cast Amount", "Cast Hue", "Shadow Hue Twist",
                     "Highlight Hue Twist", "Skin Preserve"], "sliders in the planned order")
    code = re.sub(r"//.*", "", src)
    intr = set(re.findall(r"\b(_[a-z][a-z0-9]*)\s*\(", code))
    check("_exp10f" not in code and intr <= {"_fmaxf", "_fminf", "_fabs", "_sqrtf", "_powf", "_exp2f", "_log2f",
                                             "_cosf", "_sinf", "_expf", "_saturatef", "_atan2f"},
          "only standard intrinsics, no _exp10f (%s)" % sorted(intr))
    check("@@" not in src and not re.search(r"\bdouble\b", code), "no template fields, no double precision")


def test_identity():
    section("2. identity")
    rng = random.Random(1)
    px = [tuple(f32(rng.uniform(-0.1, 1.2)) for _ in range(3)) for _ in range(200)]
    for e, i in ENC.items():
        check(run(px, uiInput=i) == px, "%s: default settings return the input bit exact" % e)
    check(run(px, amount=1, cast=1, uiBypass=1) == px, "Bypass is bit exact")
    check(run(px, hue=0.2, desat=1, balance=0.5, mid=0.3, hold=0.5, knee=0.1, black=1, cast_hue=0.6, skin=1) == px,
          "with Amount, Cast and the Twists at 0 the other sliders change nothing (bit exact)")


def test_cross():
    section("3. DCTL == reference")
    rng = random.Random(2)
    worst = {}
    for e, i in ENC.items():
        if e == "PS_DWG":
            px = [tuple(f32(rng.uniform(0.0, 0.9)) for _ in range(3)) for _ in range(60)]
        elif e == "PS_ACESCCT":
            px = [tuple(f32(rng.uniform(0.1, 0.8)) for _ in range(3)) for _ in range(60)]
        elif e == "PS_LINEAR":
            px = [tuple(f32(rng.uniform(0.0, 2.0) * rng.choice([0.05, 1.0])) for _ in range(3)) for _ in range(60)]
        else:
            px = [tuple(f32(rng.uniform(0.0, 1.0)) for _ in range(3)) for _ in range(60)]
        w = 0.0
        for _ in range(12):
            p = dict(amount=rng.uniform(0, 1), hue=rng.uniform(0, 1), desat=rng.uniform(0, 1),
                     balance=rng.uniform(-1, 1), mid=rng.uniform(-1, 1), hold=rng.uniform(0, 1),
                     knee=rng.uniform(0, 1), black=rng.uniform(0, 1), cast=rng.choice([0.0, rng.uniform(0, 1)]),
                     cast_hue=rng.uniform(0, 1), twist_s=rng.choice([0.0, rng.uniform(-1, 1)]),
                     twist_h=rng.choice([0.0, rng.uniform(-1, 1)]), skin=rng.uniform(0, 1))
            a = run(px, uiInput=i, **p)
            b = [ps.pixel(c, e, **p) for c in px]
            w = max(w, maxdiff(a, b))
        worst[e] = w
        check(w < 1e-4 if e != "PS_LINEAR" else w < 5e-4, "%s: max |DCTL - reference| = %.1e" % (e, w))


def test_ramps():
    section("4. grey ramps never reverse")
    stops = np.linspace(-12, 8, 1001)
    ramp = grey(stops)
    worst = 0.0
    for h in np.linspace(0, 1, 13)[:-1]:
        for p in (dict(amount=1, knee=0, black=1, cast=1), dict(amount=1, knee=0, black=0, balance=1),
                  dict(amount=1, knee=0, black=1, balance=-1, mid=1, cast=1, cast_hue=0.5),
                  dict(amount=1, knee=0, hold=1, black=0.5, mid=-1)):
            o = np.array(run(ramp, **dict(dict(hue=h, cast_hue=(h + 0.3) % 1), **p)))
            worst = max(worst, -np.diff(o, axis=0).min())
    check(worst < 1e-6, "every channel of a grey ramp rises, at every hue and extreme setting (worst %.1e)" % worst)


def test_controls():
    section("5. controls")
    g = grey((-3, 0, 3))
    o = run(g, amount=1, hue=0.55, black=0)
    sh, md, hi = [np.array(x) - np.array(y) for x, y in zip(o, g)]
    check(sh[2] > sh[0] + 0.02 and sh[1] > sh[0] + 0.01, "teal hue: shadows go teal %s" % np.round(sh, 3))
    check(hi[0] > hi[2] + 0.02, "and highlights the opposite, orange %s" % np.round(hi, 3))
    check(np.abs(md).max() < 0.02, "18 %% grey changes little (%.3f)" % np.abs(md).max())
    o = run(g, amount=1, balance=1)
    check(maxdiff(o[:1], g[:1]) < 1e-4 and maxdiff(o[2:], g[2:]) > 0.01, "Balance +1: highlights only")
    o = run(g, amount=1, balance=-1)
    check(maxdiff(o[2:], g[2:]) < 1e-4 and maxdiff(o[:1], g[:1]) > 0.01, "Balance -1: shadows only")
    hold = grey((-1, 1))
    check(maxdiff(run(hold, amount=1, hold=1), hold) < 1e-6 and maxdiff(run(hold, amount=1), hold) > 0.005,
          "Midtone Hold 1 keeps +-1 stop untouched")
    lo = grey((-2.5,))
    a = run(lo, amount=1, mid=1)[0]
    b = run(lo, amount=1, mid=-1)[0]
    check(chroma(a) > chroma(b) * 1.5, "Middle Grey + moves the split up: more of the image counts as shadow")
    soft = run(grey((-1.5,)), amount=1, knee=1)[0]
    hard = run(grey((-1.5,)), amount=1, knee=0)[0]
    check(chroma(hard) > chroma(soft), "Crossover Knee 0 reaches full toning sooner than Knee 1")
    deep = grey((-10,)) + [(0.0, 0.0, 0.0)]
    check(maxdiff(run(deep, amount=1, cast=1, black=1), deep) < 2e-4 and
          maxdiff(run(deep, amount=1, cast=1, black=0), deep) > 0.004, "Black Neutral 1 keeps the blacks neutral "
          "(without it they are toned)")
    c = run(grey((0,)), cast=1, cast_hue=0.08)[0]
    check(c[0] > c[2] + 0.01, "Cast Hue 0.08 warms the midtones %s" % str(np.round(c, 3)))

    # a strong colour opposite to the shadow hue (teal shadows -> a red-orange shadow colour)
    red = [col(0.05, 0.012, 0.008)]
    base = chroma(red[0])
    p0 = chroma(run(red, amount=1, desat=0, skin=0)[0])
    p1 = chroma(run(red, amount=1, desat=1, skin=0)[0])
    check(p0 < base - 0.005 and p1 >= base - 1e-4, "Desat Protect 1 stops the toning washing out an opposite "
          "colour (chroma %.3f -> %.3f off, %.3f on)" % (base, p0, p1))
    skin = [col(0.30, 0.17, 0.11), col(0.05, 0.028, 0.018)]
    s0 = run(skin, amount=1, cast=0.5, twist_s=1, twist_h=1, skin=0)
    s1 = run(skin, amount=1, cast=0.5, twist_s=1, twist_h=1, skin=1)
    check(maxdiff(s1, skin) < 0.35 * maxdiff(s0, skin), "Skin Preserve 1 keeps skin tones out (change %.3f vs %.3f)"
          % (maxdiff(s1, skin), maxdiff(s0, skin)))
    gg = grey((-3, 3))
    check(maxdiff(run(gg, twist_s=1, twist_h=-1), gg) < 1e-6, "Hue Twists leave greys alone")
    green = [col(0.01, 0.04, 0.01)]
    tw = run(green, twist_s=0.5, skin=0)[0]
    dh = (hue(tw) - hue(green[0]) + 180) % 360 - 180
    check(20 < dh < 31, "Shadow Hue Twist 0.5 turns a shadow colour by up to 30 degrees (%.1f)" % dh)


def test_curves_extremes():
    section("6. View Curves, extremes")
    rng = random.Random(4)
    pts = [(rng.randrange(1920), rng.randrange(1080), 0.4, 0.3, 0.2) for _ in range(3000)]
    off = run(pts)
    on = run(pts, uiViewCurves=1, amount=0.6)
    tone = run(pts, amount=0.6)
    line = [i for i, (a, b) in enumerate(zip(on, tone)) if a != b]
    check(5 < len(line) < 600, "View Curves draws thin lines over the frame (%d of 3000 random pixels)" % len(line))
    check(all(on[i] == tone[i] for i in range(len(pts)) if i not in line) and off[0] == (f32(0.4), f32(0.3), f32(0.2)),
          "elsewhere the picture is the toned image, unchanged")
    wild = [(0, 0, 0), (1e6, 1e6, 1e6), (-5, -5, -5), (50, -3, 0.2), (0.5, 0.5, -20), (1e-30, 0, 0)]
    ok = True
    for i in ENC.values():
        o = run(wild, uiInput=i, amount=1, cast=1, twist_s=1, twist_h=-1, desat=1, skin=1)
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
