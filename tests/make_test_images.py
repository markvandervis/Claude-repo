#!/usr/bin/env python3
"""Render the test charts and example grades in tests/images.

Everything here is written with the standard library only: the PNG writer at
the bottom of this file is about twenty lines of zlib and struct.

The charts are display-referred (the DCTL's default "Display Rec.709 sRGB"
input encoding), so the 0-1 float values map straight onto 8-bit PNG codes.

Run with:  python3 tests/make_test_images.py
"""

from __future__ import annotations

import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "reference"))

from color_mixer_reference import (  # noqa: E402
    MixerParams, PV_MASK, REGION_CENTRES, REGION_NAMES, process_pixel,
)

OUT_DIR = os.path.join(HERE, "images")

WIDTH = 480
BAND = 30
GAP = 4


# ---------------------------------------------------------------------------
# colour helpers
# ---------------------------------------------------------------------------
def hsv_to_rgb(h, s, v):
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs(math.fmod(h / 60.0, 2.0) - 1.0))
    m = v - c
    table = [(c, x, 0.0), (x, c, 0.0), (0.0, c, x), (0.0, x, c), (x, 0.0, c), (c, 0.0, x)]
    r, g, b = table[int(h // 60.0) % 6]
    return (r + m, g + m, b + m)


#: Photographic reference patches, as display-referred sRGB values.
PATCHES = [
    ("skin light",   (0.847, 0.678, 0.573)),
    ("skin mid",     (0.702, 0.502, 0.400)),
    ("skin deep",    (0.396, 0.263, 0.212)),
    ("skin shadow",  (0.271, 0.184, 0.157)),
    ("foliage sun",  (0.353, 0.478, 0.208)),
    ("foliage mid",  (0.259, 0.400, 0.196)),
    ("foliage dark", (0.145, 0.243, 0.157)),
    ("sky pale",     (0.706, 0.808, 0.902)),
    ("sky clear",    (0.361, 0.545, 0.792)),
    ("sky deep",     (0.169, 0.322, 0.616)),
    ("red cloth",    (0.784, 0.157, 0.184)),
    ("orange sign",  (0.925, 0.588, 0.106)),
    ("yellow paint", (0.949, 0.867, 0.271)),
    ("aqua tile",    (0.216, 0.706, 0.667)),
    ("purple",       (0.541, 0.310, 0.647)),
    ("magenta",      (0.847, 0.235, 0.596)),
    ("near neutral", (0.520, 0.500, 0.480)),
    ("grey card",    (0.466, 0.466, 0.466)),
]


# ---------------------------------------------------------------------------
# chart construction
# ---------------------------------------------------------------------------
def build_chart():
    """The reference chart, as a list of rows of (r, g, b) floats.

    Bands, top to bottom:
      1  full hue circle, saturation falling from 1.0 to 0.0
      2  full hue circle at fixed saturation, value falling
      3  grey ramp, then R G B and C M Y ramps
      4  a saturation gradient for each of the eight region centres
      5  photographic patches (skin, foliage, sky, saturated colours, neutrals)
      6  a near-neutral sweep of the whole hue circle at 6% saturation
    """
    rows = []

    def blank(height):
        for _ in range(height):
            rows.append([(0.08, 0.08, 0.08)] * WIDTH)

    def band(height, fn):
        for y in range(height):
            v = y / max(height - 1, 1)
            rows.append([fn(x / (WIDTH - 1.0), v) for x in range(WIDTH)])

    band(BAND * 2, lambda u, v: hsv_to_rgb(u * 360.0, 1.0 - v, 0.9))
    blank(GAP)

    band(BAND, lambda u, v: hsv_to_rgb(u * 360.0, 0.85, 1.0 - 0.85 * v))
    blank(GAP)

    band(BAND // 2, lambda u, v: (u, u, u))
    for colour in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 0)):
        band(BAND // 3, lambda u, v, c=colour: (u * c[0], u * c[1], u * c[2]))
    blank(GAP)

    def region_column(u, v):
        index = min(int(u * 8.0), 7)
        return hsv_to_rgb(REGION_CENTRES[index], v, 0.85)

    band(BAND, region_column)
    blank(GAP)

    def patch(u, v):
        index = min(int(u * len(PATCHES)), len(PATCHES) - 1)
        return PATCHES[index][1]

    band(BAND + 12, patch)
    blank(GAP)

    band(BAND // 2, lambda u, v: hsv_to_rgb(u * 360.0, 0.06, 0.55))
    return rows


def hue_strip(height, saturation=0.85, value=0.8):
    return [[hsv_to_rgb(x * 360.0 / (WIDTH - 1.0), saturation, value)
             for x in range(WIDTH)] for _ in range(height)]


def apply(rows, params):
    return [[process_pixel(px, params) for px in row] for row in rows]


# ---------------------------------------------------------------------------
# PNG output
# ---------------------------------------------------------------------------
def to_srgb_byte(value):
    return max(0, min(255, int(round(value * 255.0))))


def write_png(path, rows):
    height, width = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)                      # filter type 0 (None)
        for px in row:
            raw.append(to_srgb_byte(px[0]))
            raw.append(to_srgb_byte(px[1]))
            raw.append(to_srgb_byte(px[2]))

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(png)
    return path


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    chart = build_chart()
    written = []

    def emit(name, rows, description):
        write_png(os.path.join(OUT_DIR, name + ".png"), rows)
        written.append(name)
        print("%-32s %s" % (name + ".png", description))

    emit("00_reference_chart", chart, "untouched reference chart")

    # ---- the documented example workflows --------------------------------
    skin = MixerParams()
    skin.set_region("orange", hue=-12.0, sat=-14.0, lum=22.0)
    skin.set_region("red", hue=8.0, sat=-8.0, lum=10.0)
    emit("01_skin", apply(chart, skin), "skin: oranges opened up and calmed down")

    sky = MixerParams()
    sky.set_region("blue", hue=-18.0, sat=28.0, lum=-30.0)
    sky.set_region("aqua", hue=-25.0, sat=10.0, lum=-15.0)
    emit("02_sky", apply(chart, sky), "sky: deeper, less cyan blues")

    foliage = MixerParams()
    foliage.set_region("green", hue=-22.0, sat=-18.0, lum=12.0)
    foliage.set_region("yellow", hue=15.0, sat=-10.0, lum=8.0)
    emit("03_foliage", apply(chart, foliage), "foliage: yellower, calmer greens")

    # ---- globals ----------------------------------------------------------
    emit("04_global_saturation_plus100", apply(chart, MixerParams(global_saturation=100.0)),
         "global saturation +100")
    emit("05_global_saturation_minus100", apply(chart, MixerParams(global_saturation=-100.0)),
         "global saturation -100")
    emit("06_vibrance_plus100", apply(chart, MixerParams(vibrance=100.0)), "vibrance +100")
    emit("07_vibrance_minus100", apply(chart, MixerParams(vibrance=-100.0)), "vibrance -100")

    # ---- extremes ---------------------------------------------------------
    for name, value, label in (("08_all_plus100", 100.0, "+100"),
                               ("09_all_minus100", -100.0, "-100")):
        p = MixerParams(protect_neutrals=0.0, hue_falloff=0.0)
        p.hue = [value] * 8
        p.saturation = [value] * 8
        p.luminance = [value] * 8
        emit(name, apply(chart, p), "every one of the 24 controls at %s" % label)

    alternating = MixerParams(protect_neutrals=0.0)
    alternating.hue = [100.0, -100.0] * 4
    alternating.saturation = [100.0, -100.0] * 4
    alternating.luminance = [-100.0, 100.0] * 4
    emit("10_alternating_extremes", apply(chart, alternating),
         "neighbouring regions pushed in opposite directions")

    # ---- contact sheet: all 24 controls, +100 above, -100 below -----------
    sheet = []
    for name in REGION_NAMES:
        for kind in ("hue", "sat", "lum"):
            for value in (100.0, -100.0):
                p = MixerParams()
                p.set_region(name, **{kind: value})
                sheet += apply(hue_strip(9), p)
                if value > 0.0:
                    sheet += [[(0.08, 0.08, 0.08)] * WIDTH] * 2
            sheet += [[(0.0, 0.0, 0.0)] * WIDTH] * 3
    emit("11_all_24_controls", sheet,
         "24 controls over a hue sweep: +100 above the divider, -100 below")

    # ---- region masks -----------------------------------------------------
    masks = []
    for index in range(8):
        p = MixerParams(preview=PV_MASK, preview_region=index)
        masks += apply(hue_strip(16), p)
        masks += [[(0.0, 0.0, 0.0)] * WIDTH] * 3
    emit("12_region_masks", masks,
         "the eight region weights across the hue circle, red at the top")

    print("\n%d images written to %s" % (len(written), OUT_DIR))


if __name__ == "__main__":
    main()
