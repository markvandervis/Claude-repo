#!/usr/bin/env python3
"""Test suite for MC Film Negative and MC Film Print (and the new Core v0.6
controls).

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

  1. static checks of both DCTLs,
  2. Negative -> Print == Core, for every stock category and stock,
  3. Negative Contrast: DCTL == reference, 18 % grey never moves, grey
     ramps never reverse, every control acts in the right direction,
  4. Color Weight, Rendering Vivid,
  5. Print Only (ideal negative): neutral grey, monotonic, DCTL == reference,
  6. Show Curve, extreme inputs.

Run:  python3 tests/test_film_split.py      (builds the harnesses itself)
"""

import math
import random
import re
import sys

import numpy as np

import test_film_core as t
from test_film_core import check, section, f32, di_encode, run, m, TABLES, OUT, ENC, lin709_luma

NEG, PRT = t.NEG_HARNESS, t.PRT_HARNESS
import build_dctl  # noqa: E402

PI = {e: i for i, (e, _) in enumerate(m.PRINT_INPUTS)}
TP = {p[0]: i for i, p in enumerate(m.TONE_PRESETS)}
TONE_UI = dict(contrast="uiNegContrast", open="uiOpenClose", shadow_roll="uiShadowRoll", black_depth="uiBlackDepth",
               highlight_roll="uiHighlightRoll", latitude="uiHighlightLatitude", black_anchor="uiBlackAnchor",
               white_anchor="uiWhiteAnchor", fog="uiBaseFog", preset="uiTonePreset")


def neg_ui(ni):
    """MC Film Negative's Stock Category + stock combo for negative index ni."""
    key = m.NEGATIVES[ni][0]
    for ci, (cat, _, _, stocks) in enumerate(m.NEG_CATEGORIES):
        if key in stocks:
            return {"uiCategory": ci, "uiStock" + cat[4:].title(): stocks.index(key)}
    raise KeyError(key)


def tone_ui(tone):
    return {TONE_UI[k]: v for k, v in tone.items()}


def grey(stops):
    return [(f32(di_encode(m.MIDGRAY * 2 ** s)),) * 3 for s in stops]


def maxdiff(a, b):
    return max(abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb))


def test_static():
    section("1. static checks")
    for path, product in ((build_dctl.NEG_OUTPUT, "MC Film Negative"), (build_dctl.PRT_OUTPUT, "MC Film Print")):
        src = open(path, encoding="utf-8").read()
        lines = src.split("\n")
        banner = ["// MarkCaptures " + product, "// © 2026 Mark van der Vis / MarkCaptures", "// www.markcaptures.com"]
        name = product.split()[-1]
        check(lines[:3] == banner and [l for l in lines if l.strip()][-3:] == banner, "%s: banner at top and bottom" % name)
        entry = [l for l in lines if "float3 transform(" in l]
        check(len(entry) == 1 and entry[0].startswith("__DEVICE__ float3 transform(int p_Width"),
              "%s: transform() on one line" % name)
        params = re.findall(r"^DEFINE_UI_PARAMS\((\w+),", src, re.M)
        tips = set(re.findall(r"^DEFINE_UI_TOOLTIP\((\w+),", src, re.M))
        check(set(params) == tips and len(params) == len(set(params)), "%s: every control has one tooltip" % name)
        code = re.sub(r"//.*", "", src)
        check("_exp10f" not in code and "//@" not in src and "@@" not in src, "%s: no _exp10f, no template left" % name)
        check("CC BY-SA 4.0" in src and "Andrea Volpato" in src, "%s: stock data attribution present" % name)
        n_floats = sum(int(x) for x in re.findall(r"__CONSTANT__ (?:float|int) \w+\[(\d+)\]", src))
        check(n_floats * 4 < 60 * 1024, "%s: constant tables fit GPU constant memory (%d KB)" % (name, n_floats * 4 // 1024))
    nsrc = open(build_dctl.NEG_OUTPUT, encoding="utf-8").read()
    check("uiPrint" not in nsrc and "uiStockVision3" in nsrc, "Negative has stock categories and no print controls")
    psrc = open(build_dctl.PRT_OUTPUT, encoding="utf-8").read()
    check("uiExposure" not in psrc and "uiNegContrast" not in psrc, "Print has no negative controls")


def test_split():
    section("2. Negative -> Print == Core")
    rng = random.Random(11)
    px = [tuple(f32(di_encode(rng.uniform(0, 1.2) * rng.choice([0.05, 0.3, 1.0]))) for _ in range(3)) for _ in range(40)]
    px += grey((-8, -4, 0, 4, 8))
    worst_cin, worst_print = 0.0, 0.0
    for ni in range(len(m.NEGATIVES)):
        common = dict(uiExposure=rng.uniform(-1, 1), uiPushPull=rng.uniform(-1, 1.5), uiFilmSat=rng.uniform(0.5, 1.5),
                      uiSCyan=rng.uniform(-1, 1), uiHueTwist=rng.uniform(-10, 10),
                      uiColorWeight=rng.uniform(0, 1), uiRendering=rng.choice([0, 1]),
                      uiTonePreset=rng.randrange(len(m.TONE_PRESETS)), uiOpenClose=rng.uniform(-1, 1),
                      uiShadowRoll=rng.choice([12.0, rng.uniform(1, 8)]), uiBlackDepth=rng.uniform(0.5, 6),
                      uiHighlightRoll=rng.choice([12.0, rng.uniform(1, 8)]), uiHighlightLatitude=rng.uniform(0.5, 6),
                      uiBlackAnchor=rng.uniform(-1, 1), uiWhiteAnchor=rng.uniform(-1, 1), uiBaseFog=rng.uniform(0, 1))
        prt = dict(uiPrint=rng.randrange(len(m.PRINTS)), uiPrinterRed=rng.uniform(-6, 6),
                   uiBleach=rng.choice([0, 1, 2]), uiBleachStage=rng.choice([0, 1]), uiPrintContrast=rng.uniform(0.8, 1.2))
        cin_core = run(px, uiNegative=ni, uiOutput=OUT["OUT_CINEON"], **common)
        cin_neg = run(px, exe=NEG, **neg_ui(ni), **common)
        worst_cin = max(worst_cin, maxdiff(cin_core, cin_neg))
        one = run(px, uiNegative=ni, **common, **prt)
        two = run(cin_neg, exe=PRT, uiInput=PI["PI_CINEON"], uiNegative=ni, **prt)
        worst_print = max(worst_print, maxdiff(one, two))
    check(worst_cin == 0.0, "Negative (category + stock) gives exactly Core's Cineon negative, all %d stocks"
          % len(m.NEGATIVES))
    check(worst_print < 1e-5, "Negative -> Print == Core in one node (%.1e, the float rounding of the Cineon "
          "link)" % worst_print)


def test_tone():
    section("3. Negative Contrast")
    rng = random.Random(5)
    px = [tuple(f32(di_encode(rng.uniform(0, 1.0) * rng.choice([0.02, 0.2, 1.0, 4.0]))) for _ in range(3))
          for _ in range(30)] + grey((-7, -3, 0, 3, 7))
    worst = 0.0
    for trial in range(24):
        ni, pi = rng.randrange(len(m.NEGATIVES)), rng.randrange(len(m.PRINTS))
        tone = dict(preset=rng.randrange(len(m.TONE_PRESETS)), open=rng.uniform(-1, 1),
                    shadow_roll=rng.choice([12.0, rng.uniform(0.5, 8)]), black_depth=rng.uniform(0.25, 8),
                    highlight_roll=rng.choice([12.0, rng.uniform(0.5, 8)]), latitude=rng.uniform(0.25, 8),
                    black_anchor=rng.uniform(-1, 1), white_anchor=rng.uniform(-1, 1), fog=rng.choice([0, rng.uniform(0, 1)]))
        cw, rend, nc = rng.uniform(0, 1), rng.choice(["natural", "vivid"]), rng.uniform(0.6, 1.4)
        ui = dict(uiNegative=ni, uiPrint=pi, uiNegContrast=nc, uiColorWeight=cw, uiRendering=["natural", "vivid"].index(rend),
                  uiFilmSat=1.2, **tone_ui(tone))
        out = trial % 2 and "OUT_CINEON" or "OUT_709"
        a = run(px, uiOutput=OUT[out], **ui)
        b = [m.render_pixel(np.array(p), TABLES, ni, pi, "IN_DWG", out, neg_contrast=nc, film_sat=1.2, tone=tone,
                            color_weight=cw, rendering=rend) for p in px]
        worst = max(worst, maxdiff(a, b))
    check(worst < 2e-4, "DCTL == reference with presets, sliders, Color Weight and Rendering (%.1e)" % worst)

    mid = grey((0,))
    base = run(mid, uiOutput=OUT["OUT_CINEON"])[0]
    moved = 0.0
    for p in range(len(m.TONE_PRESETS)):
        for ui in (dict(), dict(uiOpenClose=1.0), dict(uiOpenClose=-1.0), dict(uiShadowRoll=0.5, uiBlackDepth=0.25),
                   dict(uiHighlightRoll=0.5, uiHighlightLatitude=0.25), dict(uiBlackAnchor=1, uiWhiteAnchor=-1),
                   dict(uiBaseFog=1.0)):
            o = run(mid, uiOutput=OUT["OUT_CINEON"], uiTonePreset=p, **ui)[0]
            moved = max(moved, max(abs(x - y) for x, y in zip(o, base)))
    check(moved < 1e-6, "18 %% grey's negative density never moves (presets and every slider: %.1e)" % moved)

    stops = np.linspace(-10, 7, 681)
    ramp = grey(stops)
    worst_back = 0.0
    for p in range(len(m.TONE_PRESETS)):
        for ui in (dict(), dict(uiOpenClose=1.0, uiBaseFog=1.0), dict(uiOpenClose=-1.0, uiNegContrast=1.5),
                   dict(uiShadowRoll=0.5, uiBlackDepth=0.25, uiHighlightRoll=0.5, uiHighlightLatitude=0.25),
                   dict(uiBlackAnchor=-1, uiWhiteAnchor=1), dict(uiBlackAnchor=1, uiWhiteAnchor=-1)):
            for ni in (1, 6, 12):
                y = np.array([lin709_luma(o) for o in run(ramp, uiNegative=ni, uiOutput=OUT["OUT_DWG"],
                                                           uiTonePreset=p, **ui)])
                worst_back = max(worst_back, -np.diff(y).min())
    check(worst_back < 2e-6, "grey ramps never reverse with any preset or extreme slider (%.1e)" % worst_back)

    def luma(stop, **ui):
        return lin709_luma(run(grey((stop,)), uiOutput=OUT["OUT_DWG"], **ui)[0])
    b6, b4 = luma(-6), luma(4)
    check(luma(-6, uiShadowRoll=2, uiBlackDepth=0.5) > b6 * 1.2, "Shadow Roll 2 / Black Depth 0.5 holds up the deep shadows")
    check(luma(4, uiHighlightRoll=1.5, uiHighlightLatitude=0.5) < b4 * 0.95, "Highlight Roll 1.5 / Latitude 0.5 rolls off "
          "the highlights")
    check(luma(-4, uiBlackAnchor=1) < luma(-4) * 0.97, "Black Anchor + deepens the blacks")
    check(luma(4, uiWhiteAnchor=1) > b4 * 1.02, "White Anchor + brightens the whites")
    check(luma(-6, uiBaseFog=1.0) > b6 * 1.2, "Base Fog lifts the blacks")
    lo, hi = luma(-3), luma(3)
    check(luma(3, uiOpenClose=1) / luma(-3, uiOpenClose=1) < hi / lo * 0.95, "Open + flattens the ends")
    check(luma(3, uiOpenClose=-1) / luma(-3, uiOpenClose=-1) > hi / lo * 1.05, "Close (-) steepens the ends")
    ratios = [luma(3, uiTonePreset=TP[k]) / luma(-3, uiTonePreset=TP[k]) for k in ("TP_SOFT", "TP_NATURAL", "TP_PUNCHY", "TP_HARD")]
    check(ratios == sorted(ratios), "presets get harder from Soft to Hard (contrast %s)" % ", ".join("%.1f" % r for r in ratios))
    check(run(grey((-3, 0, 3)), uiTonePreset=0) == run(grey((-3, 0, 3))), "None preset with default sliders is the stock "
          "(bit exact)")


def test_colour():
    section("4. Color Weight and Rendering")
    rng = random.Random(4)
    col = [tuple(f32(di_encode(rng.uniform(0.01, 0.5))) for _ in range(3)) for _ in range(40)]

    def lum(o):
        return [lin709_luma(x) for x in o]
    base = lum(run(col, uiOutput=OUT["OUT_DWG"]))
    hi1 = lum(run(col, uiOutput=OUT["OUT_DWG"], uiFilmSat=1.8))
    hi0 = lum(run(col, uiOutput=OUT["OUT_DWG"], uiFilmSat=1.8, uiColorWeight=0.0))
    d1 = np.mean([abs(math.log(a / b)) for a, b in zip(hi1, base)])
    d0 = np.mean([abs(math.log(a / b)) for a, b in zip(hi0, base)])
    check(d0 < d1 * 0.8, "Color Weight 0: Color Response 1.8 changes brightness less (mean %.3f vs %.3f log)" % (d0, d1))
    g = grey((-2, 0, 2))
    check(maxdiff(run(g, uiColorWeight=0.0, uiFilmSat=1.8), run(g)) < 1e-6, "Color Weight leaves greys alone")
    def sat(o):          # judged in the print's own light (DWG, no display clipping)
        lin = m.DWG_TO_REC709 @ np.array([2.0 ** (min(c, 5.0) / 0.07329248 - 7.0) - 0.0075 if c > 0.02740668
                                          else c / 10.44426855 for c in o])
        return (max(lin) - min(lin)) / max(max(lin), 1e-9)
    v = run(col, uiRendering=1, uiOutput=OUT["OUT_DWG"])
    b = run(col, uiOutput=OUT["OUT_DWG"])
    up = np.mean([sat(x) > sat(y) for x, y in zip(v, b)])
    check(up > 0.9, "Rendering Vivid is more saturated (%.0f %% of colours)" % (100 * up))
    check(maxdiff(run(g, uiRendering=1), run(g)) < 1e-6, "Rendering Vivid leaves greys alone")


def test_print_only():
    section("5. Print Only (ideal negative)")
    gm = [(f32(di_encode(m.MIDGRAY)),) * 3]
    worst, lv = 0.0, []
    for pi in range(len(m.PRINTS)):
        o = run(gm, exe=PRT, uiInput=PI["PI_DWG"], uiPrint=pi)[0]
        worst = max(worst, max(o) - min(o))
        lv.append(abs(o[1] - run(gm, uiPrint=pi)[0][1]))
    check(worst < 2e-3, "18 %% grey prints neutral on every print stock (%.1e)" % worst)
    check(max(lv) < 0.03, "18 %% grey prints at the same level as through a real negative (within %.3f)" % max(lv))
    ramp = grey(np.linspace(-10, 7, 681))
    wb = 0.0
    for pi in range(len(m.PRINTS)):
        for ui in (dict(), dict(uiBleach=2, uiBleachStrength=1.0), dict(uiBleach=1, uiBleachStage=1),
                   dict(uiPrintContrast=1.5)):
            y = np.array([lin709_luma(o) for o in run(ramp, exe=PRT, uiInput=PI["PI_DWG"], uiPrint=pi,
                                                       uiOutput=OUT["OUT_DWG"], **ui)])
            wb = max(wb, -np.diff(y).min())
    check(wb < 2e-6, "print-only grey ramps never reverse (%.1e)" % wb)
    rng = random.Random(3)
    px = [tuple(f32(di_encode(rng.uniform(0, 1.0) * rng.choice([0.05, 0.3, 1.0, 3.0]))) for _ in range(3))
          for _ in range(40)]
    worst = 0.0
    for pi in range(len(m.PRINTS)):
        bleach = rng.choice(["off", "authentic", "grunge"])
        stage = rng.choice(["print", "negative"])
        ui = dict(uiPrint=pi, uiPrinterRed=rng.uniform(-8, 8), uiPrintExposure=rng.uniform(-6, 6),
                  uiPrintContrast=rng.uniform(0.7, 1.3), uiBleach=["off", "authentic", "grunge"].index(bleach),
                  uiBleachStage=["print", "negative"].index(stage), uiWhite=rng.choice([0, 1, 2]))
        a = run(px, exe=PRT, uiInput=PI["PI_DWG"], **ui)
        b = [m.render_pixel(np.array(p), TABLES, None, pi, "IN_DWG", "OUT_709", 0.0, 0.0, (ui["uiPrinterRed"], 0, 0),
                            ui["uiPrintExposure"], 1.0, ui["uiPrintContrast"], True, 1.0, bleach, stage, 0.7, 1.0,
                            True, ui["uiWhite"]) for p in px]
        worst = max(worst, maxdiff(a, b))
    check(worst < 2e-4, "Print Only: DCTL == reference (%.1e)" % worst)
    lin = (0.3, 0.12, 0.05)
    dwg = np.linalg.solve(m.DWG_TO_REC709, np.array(lin))
    outs = [run([tuple(f32(di_encode(v)) for v in dwg)], exe=PRT, uiInput=PI["PI_DWG"])[0],
            run([tuple(f32(v) for v in lin)], exe=PRT, uiInput=PI["PI_LINEAR"])[0],
            run([tuple(f32(v ** (1 / 2.4)) for v in lin)], exe=PRT, uiInput=PI["PI_709"])[0]]
    check(maxdiff(outs[:1] * 2, outs[1:]) < 2e-3, "Print Only: DWG, Linear and Rec709 inputs agree")
    r = run(gm, exe=PRT, uiInput=PI["PI_DWG"], uiPrinterRed=10)[0]
    check(r[0] < r[1] and r[0] < r[2], "Print Only: Printer Red + makes the print less red")


def test_overlay_extremes():
    section("6. Show Curve, extremes")
    px = [(0, 0, 0.3, 0.3, 0.3), (5, 5, 0.3, 0.3, 0.3), (1500, 900, 0.3, 0.3, 0.3)]
    off = run(px, exe=NEG, **neg_ui(1))
    on = run(px, exe=NEG, uiShowCurve=1, **neg_ui(1))
    check(on[0] == off[0] and on[2] == off[2], "Show Curve leaves the picture outside the box bit exact")
    box = [(x, y, 0.3, 0.3, 0.3) for x in range(60, 700, 7) for y in range(45, 370, 7)]
    ob = np.array(run(box, exe=NEG, uiShowCurve=1, **neg_ui(1)))
    cols = set(tuple(np.round(o, 4)) for o in ob)
    check(np.all(np.isfinite(ob)) and len(cols) >= 5, "Show Curve draws the box, the grid and the curves (%d colours)" % len(cols))
    wild = [(0, 0, 0), (1e6, 1e6, 1e6), (-5, -5, -5), (50, -3, 0.2), (0.5, 0.5, -20)]
    ok = True
    for ni in range(len(m.NEGATIVES)):
        for p in range(len(m.TONE_PRESETS)):
            o = run(wild, exe=NEG, **neg_ui(ni), uiTonePreset=p, uiExposure=4, uiPushPull=2.5, uiOpenClose=-1,
                    uiShadowRoll=0.5, uiBlackDepth=0.25, uiHighlightRoll=0.5, uiHighlightLatitude=0.25, uiBaseFog=1,
                    uiBlackAnchor=1, uiWhiteAnchor=1, uiColorWeight=0, uiRendering=1, uiFilmSat=2)
            ok &= all(math.isfinite(v) for x in o for v in x)
    for pi in range(len(m.PRINTS)):
        for inp in range(len(m.PRINT_INPUTS)):
            o = run(wild, exe=PRT, uiInput=inp, uiPrint=pi, uiBleach=2, uiBleachStrength=1, uiSilverContrast=2)
            ok &= all(math.isfinite(v) for x in o for v in x)
    check(ok, "finite output for extreme inputs and settings, Negative and Print")


def main():
    t.build()
    test_static()
    test_split()
    test_tone()
    test_colour()
    test_print_only()
    test_overlay_extremes()
    print("\n%d checks, %d failed" % (t._n, len(t._fail)))
    return 1 if t._fail else 0


if __name__ == "__main__":
    sys.exit(main())
