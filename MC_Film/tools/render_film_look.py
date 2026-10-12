#!/usr/bin/env python3
"""Render the full MC Film chain on a 1920x1080 synthetic scene for visual
checking: Halation -> Core (negative) -> Grain -> Core (print), per gauge.
Writes docs/film_look.png (downscaled frame + 1:1 crops).

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mcfilm_model as m   # noqa: E402
import render_chart        # noqa: E402

W, H = 1920, 1080
T = os.path.join(ROOT, "tests")


def scene():
    img = np.zeros((H, W, 3))
    small = render_chart.scene()                          # 480 x 270 chart, scaled x2
    img[:540, :960] = np.kron(small, np.ones((2, 2, 1)))
    # night scene: dark blue-ish background, warm lamps, a bright window
    yy, xx = np.mgrid[0:H, 0:W]
    img[:, 960:] = np.array([0.004, 0.006, 0.012])
    for (cx, cy, r, col) in ((1150, 200, 4, (40, 30, 18)), (1350, 260, 2.5, (60, 50, 40)),
                             (1600, 180, 6, (30, 20, 10)), (1800, 330, 3, (20, 40, 60))):
        d = np.hypot(xx - cx, yy - cy)
        img[d < r] = col
    img[420:520, 1250:1450] = (6.0, 5.0, 4.0)             # window
    # lower half: skin ramp and a soft sky gradient for grain in smooth areas
    for x in range(W):
        img[560:820, x] = np.array([0.50, 0.33, 0.25]) ** 2.2 * 2 ** (-3 + 6 * x / W)
        img[820:, x] = np.array([0.18, 0.30, 0.55]) * (0.15 + 0.85 * x / W)
    return img


def frame_io(exe, img, args, frame=True):
    flat = img.reshape(-1, 3)
    head = "%d %d\n" % (W, H) if frame else ""
    payload = head + "\n".join("%r %r %r" % tuple(p) for p in flat) + "\n"
    r = subprocess.run([os.path.join(T, exe)] + args, input=payload, capture_output=True, text=True, check=True)
    return np.array([[float.fromhex(v) for v in l.split()] for l in r.stdout.splitlines()]).reshape(H, W, 3)


def chain(lin, gauge, neg=1, prt=0):
    dwg = (np.linalg.inv(m.DWG_TO_REC709) @ lin.reshape(-1, 3).T).T
    enc = render_chart.di_encode(dwg).reshape(H, W, 3)
    g = ["uiGauge=%d" % gauge]
    hal = frame_io("fx_halation", enc, g + ["uiHalAmount=0.3"])
    negc = frame_io("mcf_harness", hal, ["uiNegative=%d" % neg, "uiOutput=5"], frame=False)
    grn = frame_io("fx_grain", negc, g + ["uiNegative=%d" % neg, "uiSeed=3"])
    return frame_io("mcf_harness", grn, ["uiNegative=%d" % neg, "uiPrint=%d" % prt, "uiInput=4"], frame=False)


def main():
    img = scene()
    rows = []
    for gauge, name in ((3, "Super 35"), (2, "Super 16"), (0, "Super 8")):
        out = np.clip(chain(img, gauge), 0, 1)
        rows.append((name, out))
        print("rendered", name)
    cw, ch = 400, 300
    sheet = Image.new("RGB", (960 + 2 * cw + 40, len(rows) * (540 + 30) + 10), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (name, out) in enumerate(rows):
        y0 = 10 + i * 570
        im = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
        sheet.paste(im.resize((960, 540), Image.LANCZOS), (10, y0 + 20))
        sheet.paste(im.crop((1150, 380, 1150 + cw, 380 + ch)), (980, y0 + 20))       # window + lamps, 1:1
        sheet.paste(im.crop((300, 620, 300 + cw, 620 + ch)), (990 + cw, y0 + 20))    # skin + sky, 1:1
        d.text((10, y0 + 4), "250D -> 2383, %s (halation 0.3, grain 1.0) - full frame" % name, fill=(230, 230, 230))
        d.text((980, y0 + 4), "1:1 crops", fill=(230, 230, 230))
    out = os.path.join(ROOT, "docs", "film_look.png")
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
