#!/usr/bin/env python3
"""Render a synthetic test chart through MC Film Core (the compiled DCTL) for
a set of stock combinations, for visual checking.  Writes docs/chart.png.

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
"""
import math
import os
import subprocess
import sys
import warnings

import numpy as np
from PIL import Image, ImageDraw

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mcfilm_model as m  # noqa: E402

W, H = 480, 270
HARNESS = os.path.join(ROOT, "tests", "mcf_harness")
COMBOS = [("Kodak Vision3 250D", "Kodak 2383"), ("Kodak Vision3 500T", "Kodak 2383"),
          ("Kodak Vision3 50D", "Kodak 2393"), ("Kodak Portra 400", "Kodak Portra Endura"),
          ("Fujifilm Pro 400H", "Fujifilm Crystal Archive"), ("Kodak Ektar 100", "Kodak Endura Premier"),
          ("Kodak Gold 200", "Kodak Portra Endura")]


def hsv(h, s, v):
    h %= 360.0
    c = v * s
    x = c * (1 - abs(math.fmod(h / 60.0, 2) - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return np.array((r + v - c, g + v - c, b + v - c))


def checker_linear():
    import colour
    cc = colour.CCS_COLOURCHECKERS["ColorChecker24 - After November 2014"]
    out = []
    for name, xyy in cc.data.items():
        xyz = colour.xyY_to_XYZ(xyy)
        xyz = colour.adaptation.chromatic_adaptation_VonKries(xyz, colour.xy_to_XYZ(cc.illuminant),
                                                              colour.xy_to_XYZ([0.3127, 0.3290]))
        out.append(np.linalg.solve(m.REC709_TO_XYZ, xyz))
    return out


def scene():
    img = np.zeros((H, W, 3))
    # row 0: grey ramp, -8 .. +6 stops around 18 %
    for x in range(W):
        img[0:60, x] = m.MIDGRAY * 2 ** (-8 + 14 * x / (W - 1))
    # row 1: hue sweep at mid exposure, saturation rising downwards
    for y in range(60, 120):
        for x in range(W):
            img[y, x] = hsv(360 * x / W, 0.25 + 0.65 * (y - 60) / 59, 1.0) * 0.30
    # row 2: colour checker
    cc = checker_linear()
    for i, c in enumerate(cc):
        x0, y0 = (i % 12) * (W // 12), 120 + (i // 12) * 45
        img[y0:y0 + 45, x0:x0 + W // 12] = np.maximum(c, 0)
    # row 3: skin ramp (several skin tones, -2 .. +3 stops)
    skins = [(0.50, 0.33, 0.25), (0.42, 0.26, 0.18), (0.26, 0.15, 0.10), (0.60, 0.45, 0.38)]
    for x in range(W):
        e = 2 ** (-2 + 5 * x / (W - 1))
        for j, s in enumerate(skins):
            img[210 + j * 15:225 + j * 15, x] = np.array(s) ** 2.2 * e * 0.9
    return img


def di_encode(x):
    return np.where(x > 0.00262409, (np.log2(np.maximum(x, 1e-12) + 0.0075) + 7.0) * 0.07329248, x * 10.44426855)


def run(img_lin, neg, prt, extra=()):
    dwg = (np.linalg.inv(m.DWG_TO_REC709) @ img_lin.reshape(-1, 3).T).T
    enc = di_encode(dwg)
    payload = "\n".join("%.9g %.9g %.9g" % tuple(float(v) for v in p) for p in enc) + "\n"
    args = ["uiNegative=%d" % neg, "uiPrint=%d" % prt] + list(extra)
    r = subprocess.run([HARNESS] + args, input=payload, capture_output=True, text=True, check=True)
    out = np.array([[float.fromhex(v) for v in l.split()] for l in r.stdout.splitlines()])
    return out.reshape(H, W, 3)


FEATURES = [("250D -> 2383", []),
            ("Bleach Authentic, print", ["uiBleach=1", "uiBleachStrength=1"]),
            ("Bleach Grunge, print", ["uiBleach=2", "uiBleachStrength=1"]),
            ("Bleach Authentic, negative", ["uiBleach=1", "uiBleachStage=1", "uiBleachStrength=1"]),
            ("Film Saturation 0.6", ["uiFilmSat=0.6"]),
            ("Film Saturation 1.4, Push +1", ["uiFilmSat=1.4", "uiPushPull=1"]),
            ("Crossover: Shadow Cyan +1.2, Highlight Yellow +1, Hold 0.3",
             ["uiSCyan=1.2", "uiHYellow=1", "uiXHold=0.3"]),
            ("Hue Twist +12, Richness +0.6", ["uiHueTwist=12", "uiRichness=0.6"]),
            ("Vibrance +0.8, Chroma Rolloff 0.8", ["uiVibrance=0.8", "uiChromaRolloff=0.8"]),
            ("Highlight Desaturation 1, Exposure +1.5", ["uiHlDesat=1", "uiExposure=1.5"])]


def sheet_of(panels, path):
    cols = 2
    rows = (len(panels) + 1) // 2
    sheet = Image.new("RGB", (cols * (W + 10) + 10, rows * (H + 34) + 10), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (title, p) in enumerate(panels):
        x0, y0 = 10 + (i % cols) * (W + 10), 10 + (i // cols) * (H + 34)
        sheet.paste(Image.fromarray((np.clip(p, 0, 1) * 255 + 0.5).astype(np.uint8)), (x0, y0 + 20))
        d.text((x0, y0 + 4), title, fill=(230, 230, 230))
    sheet.save(path)
    print("wrote", path)


def main():
    img = scene()
    neg250, p2383 = [n for _, n, _ in m.NEGATIVES].index("Kodak Vision3 250D"), 0
    sheet_of([(t, run(img, neg250, p2383, a)) for t, a in FEATURES], os.path.join(ROOT, "docs", "features.png"))
    digital = np.clip(img, 0, 1) ** (1 / 2.4)
    names_neg = [n for _, n, _ in m.NEGATIVES]
    names_prt = [n for _, n, _ in m.PRINTS]
    panels = [("Digital (clipped, gamma 2.4)", digital)]
    for neg, prt in COMBOS:
        panels.append(("%s -> %s" % (neg, prt), run(img, names_neg.index(neg), names_prt.index(prt))))
    cols = 2
    rows = (len(panels) + 1) // 2
    sheet = Image.new("RGB", (cols * (W + 10) + 10, rows * (H + 34) + 10), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (title, p) in enumerate(panels):
        x0, y0 = 10 + (i % cols) * (W + 10), 10 + (i // cols) * (H + 34)
        sheet.paste(Image.fromarray((np.clip(p, 0, 1) * 255 + 0.5).astype(np.uint8)), (x0, y0 + 20))
        d.text((x0, y0 + 4), title, fill=(230, 230, 230))
    out = os.path.join(ROOT, "docs", "chart.png")
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
