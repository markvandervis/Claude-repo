#!/usr/bin/env python3
"""Test suite for Lightroom_Color_Mixer.dctl.

Covers:
  * static validation of the DCTL source (UI declarations, entry point,
    self-containedness, combo enumerations vs. the test shim),
  * cross-validation of the compiled DCTL against the Python reference,
  * identity / bypass / amount behaviour,
  * every one of the 24 per-colour controls, individually,
  * global saturation, vibrance, neutral protection, gamut behaviour,
  * extreme values, numerical stability and hue continuity.

Run with:  python3 tests/run_tests.py
"""

from __future__ import annotations

import math
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "reference"))

from color_mixer_reference import (  # noqa: E402
    ENC_DISPLAY, ENC_LOG, ENC_LINEAR, ENC_DWG, PV_MASK, PV_ISOLATE,
    REGION_NAMES, REGION_CENTRES, MixerParams, DWG_TO_REC709,
    process_pixel, region_weights, luma, saturation_measure, rgb_to_hue,
    di_encode,
)

DCTL_PATH = os.path.join(ROOT, "Lightroom_Color_Mixer.dctl")
HARNESS = os.path.join(HERE, "dctl_harness")

_failures = []
_tests_run = 0


def params(**kwargs):
    """MixerParams defaulting to the display domain.

    The DCTL itself defaults to DaVinci WG Intermediate, which is where it is
    meant to sit in a colour-managed node tree.  Most of the tests below are
    written against display-referred values, so they say so explicitly rather
    than inheriting whichever default the DCTL happens to ship with.
    """
    kwargs.setdefault("encoding", ENC_DISPLAY)
    return MixerParams(**kwargs)


# ---------------------------------------------------------------------------
# tiny test framework
# ---------------------------------------------------------------------------
def check(condition, message):
    global _tests_run
    _tests_run += 1
    if not condition:
        _failures.append(message)
        print("  FAIL  " + message)
    return bool(condition)


def section(title):
    print("\n=== %s ===" % title)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def f32(value):
    """Round a Python float to the nearest 32-bit float.

    The DCTL runs in 32-bit float, so every test pixel is quantised first.  That
    keeps the hex round trip through the harness exact and lets the identity
    tests compare for true bit equality rather than for closeness.
    """
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f32px(pixels):
    return [tuple(f32(v) for v in px) for px in pixels]


def hsv_to_rgb(h, s, v):
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs(math.fmod(h / 60.0, 2.0) - 1.0))
    m = v - c
    table = [(c, x, 0.0), (x, c, 0.0), (0.0, c, x), (0.0, x, c), (x, 0.0, c), (c, 0.0, x)]
    r, g, b = table[int(h // 60.0) % 6]
    return (f32(r + m), f32(g + m), f32(b + m))


def run_dctl(settings: MixerParams, pixels):
    """Run the compiled DCTL harness over a list of pixels."""
    payload = "".join("%s %s %s\n" % (a.hex(), b.hex(), c.hex()) for a, b, c in pixels)
    result = subprocess.run([HARNESS] + settings.to_dctl_args(), input=payload,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("harness failed: " + result.stderr)
    out = []
    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        out.append(tuple(float.fromhex(p) for p in parts))
    return out


def run_reference(settings: MixerParams, pixels):
    return [process_pixel(px, settings) for px in pixels]


def max_abs_diff(a, b):
    return max(max(abs(x - y) for x, y in zip(pa, pb)) for pa, pb in zip(a, b))


def chroma(px):
    return max(px) - min(px)


def finite(pixels):
    return all(math.isfinite(v) for px in pixels for v in px)


# ---------------------------------------------------------------------------
# test pixel sets
# ---------------------------------------------------------------------------
def build_pixel_set():
    """A broad, deliberately awkward set of test pixels."""
    px = []

    # grayscale ramp, including exact black and white
    for i in range(21):
        v = i / 20.0
        px.append((v, v, v))

    # full hue wheel at several saturations and values
    for h in range(0, 360, 6):
        for s in (0.15, 0.5, 0.9, 1.0):
            for v in (0.2, 0.55, 0.95):
                px.append(hsv_to_rgb(h, s, v))

    # primaries / secondaries at full strength
    px += [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1)]

    # photographic samples (display-referred, approximate sRGB values)
    px += [
        (0.847, 0.678, 0.573),   # light skin
        (0.702, 0.502, 0.400),   # mid skin
        (0.396, 0.263, 0.212),   # dark skin
        (0.898, 0.729, 0.596),   # warm highlight on skin
        (0.259, 0.400, 0.196),   # foliage green
        (0.353, 0.478, 0.208),   # sunlit foliage
        (0.145, 0.243, 0.157),   # shadow foliage
        (0.361, 0.545, 0.792),   # clear sky
        (0.169, 0.322, 0.616),   # deep sky
        (0.706, 0.808, 0.902),   # pale horizon
        (0.784, 0.157, 0.184),   # red clothing
        (0.925, 0.588, 0.106),   # saturated orange
        (0.949, 0.867, 0.271),   # yellow object
        (0.541, 0.310, 0.647),   # purple
        (0.847, 0.235, 0.596),   # magenta
        (0.216, 0.706, 0.667),   # aqua
    ]

    # near-neutral, near-black and near-white edge cases
    px += [
        (0.5, 0.5005, 0.4995), (0.001, 0.001, 0.001), (0.0, 0.0, 1e-7),
        (1.0, 1.0, 0.999), (1e-8, 0.0, 0.0), (0.5, 0.5, 0.5),
    ]

    # values outside 0-1: HDR highlights and negative (out of gamut) channels
    px += [
        (4.0, 3.2, 2.5), (12.0, 1.0, 0.5), (1.4, 1.4, 1.4),
        (0.6, -0.05, 0.2), (-0.02, 0.4, 0.9), (0.3, 0.2, -0.3),
        (2.0, -0.1, -0.1),
    ]
    return f32px(px)


PIXELS = build_pixel_set()

LOG_PIXELS = f32px([(0.09, 0.09, 0.09), (0.5, 0.42, 0.38), (0.62, 0.55, 0.40),
              (0.30, 0.45, 0.33), (0.40, 0.48, 0.60), (0.72, 0.60, 0.52),
              (0.10, 0.30, 0.55), (0.55, 0.30, 0.45), (0.95, 0.90, 0.80)])

def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _matvec(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def _npm(primaries, white):
    """RGB -> XYZ from chromaticities, by the standard derivation.

    Derived here from first principles so that the test's forward matrix is
    genuinely independent of the inverse matrix baked into the DCTL.
    """
    (xr, yr), (xg, yg), (xb, yb) = primaries
    xw, yw = white
    m = [[xr / yr, xg / yg, xb / yb],
         [1.0, 1.0, 1.0],
         [(1 - xr - yr) / yr, (1 - xg - yg) / yg, (1 - xb - yb) / yb]]
    w = [xw / yw, 1.0, (1 - xw - yw) / yw]
    rows = [row[:] + [w[i]] for i, row in enumerate(m)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(3):
            if r != col:
                f = rows[r][col] / rows[col][col]
                for k in range(col, 4):
                    rows[r][k] -= f * rows[col][k]
    scale = [rows[i][3] / rows[i][i] for i in range(3)]
    return [[m[i][j] * scale[j] for j in range(3)] for i in range(3)]


def _inverse(a):
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
           - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    return [[(a[(i + 1) % 3][(j + 1) % 3] * a[(i + 2) % 3][(j + 2) % 3]
              - a[(i + 1) % 3][(j + 2) % 3] * a[(i + 2) % 3][(j + 1) % 3]) / det
             for i in range(3)] for j in range(3)]


D65 = (0.3127, 0.3290)
REC709_PRIMARIES = [(0.640, 0.330), (0.300, 0.600), (0.150, 0.060)]
DWG_PRIMARIES = [(0.8000, 0.3130), (0.1682, 0.9877), (0.0790, -0.1155)]

#: linear Rec.709 -> linear DaVinci Wide Gamut, derived from the chromaticities
REC709_TO_DWG = _matmul(_inverse(_npm(DWG_PRIMARIES, D65)), _npm(REC709_PRIMARIES, D65))


def srgb_to_linear(x):
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def rec709_display_to_dwg_di(rgb):
    """What CST IN puts on the wire for a colour we know in Rec.709 terms."""
    lin = _matvec(REC709_TO_DWG, [srgb_to_linear(v) for v in rgb])
    return tuple(f32(di_encode(v)) for v in lin)


LINEAR_PIXELS = f32px([(0.18, 0.18, 0.18), (0.30, 0.12, 0.05), (0.05, 0.14, 0.04),
                 (0.10, 0.20, 0.55), (2.5, 1.8, 1.2), (0.002, 0.001, 0.0005),
                 (0.0, 0.0, 0.0), (16.0, 8.0, 4.0), (0.5, -0.01, 0.02)])


#: Photographic colours, specified in Rec.709 display terms and carried into
#: DaVinci Wide Gamut / DaVinci Intermediate the way CST IN would carry them.
DWG_REFERENCE = [
    ("skin light",   (0.847, 0.678, 0.573)),
    ("skin mid",     (0.702, 0.502, 0.400)),
    ("skin deep",    (0.396, 0.263, 0.212)),
    ("foliage sun",  (0.353, 0.478, 0.208)),
    ("foliage mid",  (0.259, 0.400, 0.196)),
    ("foliage dark", (0.145, 0.243, 0.157)),
    ("sky clear",    (0.361, 0.545, 0.792)),
    ("sky deep",     (0.169, 0.322, 0.616)),
    ("red cloth",    (0.784, 0.157, 0.184)),
    ("orange sign",  (0.925, 0.588, 0.106)),
    ("yellow paint", (0.949, 0.867, 0.271)),
    ("aqua tile",    (0.216, 0.706, 0.667)),
    ("purple",       (0.541, 0.310, 0.647)),
    ("magenta",      (0.847, 0.235, 0.596)),
]

DWG_PIXELS = ([rec709_display_to_dwg_di(rgb) for _, rgb in DWG_REFERENCE]
              + [rec709_display_to_dwg_di(hsv_to_rgb(h, s, v))
                 for h in range(0, 360, 15) for s in (0.2, 0.7, 1.0) for v in (0.25, 0.8)]
              + f32px([(0.09, 0.09, 0.09), (0.5, 0.5, 0.5), (0.95, 0.95, 0.95),
                       (0.0, 0.0, 0.0), (1.2, 1.1, 1.0), (0.4, -0.05, 0.2)]))


# ===========================================================================
# 1. static validation of the DCTL source
# ===========================================================================
def parse_ui_params(source):
    """Parse every DEFINE_UI_PARAMS declaration into name -> [fields]."""
    declared = {}
    pattern = re.compile(r"DEFINE_UI_PARAMS\s*\((.*?)\)\s*$", re.M)
    for match in pattern.finditer(source):
        body = match.group(1)
        # split on commas that are not inside braces
        parts, depth, current = [], 0, ""
        for ch in body:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += ch
        parts.append(current.strip())
        declared[parts[0]] = parts
    return declared


def test_static_source():
    section("DCTL source validation")
    source = open(DCTL_PATH).read()

    check("#include" not in source,
          "DCTL must be self contained (no #include) so it can be dropped into the LUT folder")

    # Resolve matches this declaration line by line rather than parsing C, so the
    # whole signature has to sit on one line in exactly this form.  Wrapping the
    # parameter list is legal C but makes Resolve report
    #   "wrong argument int p_Width in Transform DCTL"
    # and refuse to build, so the exact single-line text is what gets checked.
    expected_entry = ("__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, "
                      "int p_Y, float p_R, float p_G, float p_B)")
    check(any(line.rstrip() == expected_entry for line in source.split("\n")),
          "the transform() entry point must appear on a single line exactly as:\n    "
          + expected_entry)
    check(len(re.findall(r"\btransform\s*\(", source)) == 1,
          "'transform(' should appear exactly once, so Resolve's line-based parser "
          "cannot latch onto the wrong occurrence")

    # every function definition must carry __DEVICE__
    for match in re.finditer(r"^\s*(?:static\s+)?(float|float2|float3|float4|int|void)\s+"
                             r"([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", source, re.M):
        check(False, "function %s is defined without a __DEVICE__ qualifier" % match.group(2))

    # same line-based parser, same hazard: a wrapped DEFINE_UI_PARAMS would not
    # be seen either
    for number, line in enumerate(source.split("\n"), 1):
        if "DEFINE_UI_PARAMS" in line and not line.rstrip().endswith(")"):
            check(False, "DEFINE_UI_PARAMS on line %d must fit on one line" % number)

    declared = parse_ui_params(source)
    check(len(declared) == 35, "expected 35 UI parameters, found %d" % len(declared))

    pretty = ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")
    for name in pretty:
        for suffix in ("Hue", "Sat", "Lum"):
            key = "ui%s%s" % (name, suffix)
            if not check(key in declared, "missing UI parameter %s" % key):
                continue
            parts = declared[key]
            check(parts[2] == "DCTLUI_SLIDER_FLOAT", "%s must be a float slider" % key)
            check(float(parts[3]) == 0.0, "%s must default to 0" % key)
            check(float(parts[4]) == -100.0, "%s must have minimum -100" % key)
            check(float(parts[5]) == 100.0, "%s must have maximum +100" % key)

    for key, default, lo, hi in (("uiGlobalSat", 0.0, -100.0, 100.0),
                                 ("uiVibrance", 0.0, -100.0, 100.0),
                                 ("uiAmount", 100.0, 0.0, 100.0),
                                 ("uiProtectNeutrals", 35.0, 0.0, 100.0),
                                 ("uiPreserveLum", 75.0, 0.0, 100.0),
                                 ("uiHueFalloff", 50.0, 0.0, 100.0),
                                 ("uiSatProtect", 50.0, 0.0, 100.0)):
        if not check(key in declared, "missing UI parameter %s" % key):
            continue
        parts = declared[key]
        check(float(parts[3]) == default, "%s default should be %g" % (key, default))
        check(float(parts[4]) == lo and float(parts[5]) == hi,
              "%s range should be %g..%g" % (key, lo, hi))

    check(declared.get("uiBypass", [None, None, None])[2] == "DCTLUI_CHECK_BOX",
          "Bypass must be a check box")

    # combo enumerations must match the enumerations declared in the shim
    shim = open(os.path.join(HERE, "dctl_shim.h")).read()
    for key, expected in (("uiEncoding", ["ENC_DISPLAY", "ENC_LOG", "ENC_LINEAR", "ENC_DWG"]),
                          ("uiPreview", ["PV_OFF", "PV_MASK", "PV_ISOLATE"]),
                          ("uiPreviewRegion", ["PR_RED", "PR_ORANGE", "PR_YELLOW", "PR_GREEN",
                                               "PR_AQUA", "PR_BLUE", "PR_PURPLE", "PR_MAGENTA"])):
        parts = declared[key]
        names = [n.strip() for n in parts[4].strip("{}").split(",")]
        labels = [n.strip() for n in parts[5].strip("{}").split(",")]
        check(names == expected, "%s enumeration should be %s, found %s" % (key, expected, names))
        check(len(labels) == len(names), "%s label count must match enumeration count" % key)
        for index, name in enumerate(names):
            check(re.search(r"\b%s\s*=\s*%d\b" % (name, index), shim) is not None,
                  "test shim is out of sync with the DCTL for %s" % name)


# ===========================================================================
# 2. cross-validation: compiled DCTL vs. Python reference
# ===========================================================================
def test_cross_validation():
    section("DCTL vs. Python reference")

    cases = []

    base = params()
    cases.append(("defaults", base, PIXELS))

    for i, name in enumerate(REGION_NAMES):
        for kind, value in (("hue", 70.0), ("sat", -60.0), ("lum", 45.0)):
            p = params()
            p.set_region(name, **{kind: value})
            cases.append(("%s %s" % (name, kind), p, PIXELS))

    p = params(global_saturation=60.0, vibrance=-40.0)
    cases.append(("global sat + vibrance", p, PIXELS))

    p = params(hue_falloff=0.0, protect_neutrals=100.0, saturation_protection=100.0,
                    preserve_luminance=100.0)
    p.hue = [100.0] * 8
    p.saturation = [100.0] * 8
    p.luminance = [-100.0] * 8
    cases.append(("all extreme", p, PIXELS))

    p = params(encoding=ENC_LOG, protect_neutrals=10.0)
    p.set_region("orange", hue=-30.0, sat=40.0, lum=60.0)
    cases.append(("log domain", p, LOG_PIXELS))

    p = params(encoding=ENC_LINEAR)
    p.set_region("blue", hue=25.0, sat=-50.0, lum=-70.0)
    cases.append(("linear domain", p, LINEAR_PIXELS))

    p = params(encoding=ENC_DWG, protect_neutrals=20.0)
    p.set_region("green", hue=-40.0, sat=-35.0, lum=25.0)
    p.set_region("orange", hue=15.0, sat=20.0, lum=-10.0)
    cases.append(("davinci wide gamut", p, DWG_PIXELS))

    p = params(encoding=ENC_DWG, vibrance=70.0, global_saturation=-30.0)
    cases.append(("davinci wide gamut globals", p, DWG_PIXELS))

    p = params(amount=37.0, vibrance=80.0)
    cases.append(("partial amount", p, PIXELS))

    p = params(preview=PV_MASK, preview_region=1)
    cases.append(("preview mask", p, PIXELS))

    p = params(preview=PV_ISOLATE, preview_region=5, global_saturation=30.0)
    cases.append(("preview isolate", p, PIXELS))

    worst = 0.0
    for label, case, pixels in cases:
        got = run_dctl(case, pixels)
        want = run_reference(case, pixels)
        if not check(len(got) == len(pixels), "%s: harness returned %d of %d pixels"
                     % (label, len(got), len(pixels))):
            continue
        check(finite(got), "%s: DCTL produced a non-finite value" % label)
        diff = max_abs_diff(got, want)
        scale = max(1.0, max(abs(v) for px in pixels for v in px))
        worst = max(worst, diff / scale)
        check(diff / scale < 2e-5,
              "%s: DCTL and reference disagree by %.3g (relative %.3g)" % (label, diff, diff / scale))
    print("  worst relative disagreement across %d cases: %.3g" % (len(cases), worst))


# ===========================================================================
# 3. identity, bypass and amount
# ===========================================================================
def test_identity():
    section("identity / bypass / amount")

    for encoding, label, pixels in ((ENC_DISPLAY, "display", PIXELS),
                                    (ENC_LOG, "log", LOG_PIXELS),
                                    (ENC_LINEAR, "linear", LINEAR_PIXELS),
                                    (ENC_DWG, "davinci wide gamut", DWG_PIXELS)):
        got = run_dctl(params(encoding=encoding), pixels)
        check(got == pixels, "%s: neutral settings must be a bit exact identity" % label)

    # amount = 0 with everything pushed to the extremes
    p = params(amount=0.0, global_saturation=100.0, vibrance=-100.0)
    p.hue = [100.0] * 8
    p.saturation = [-100.0] * 8
    p.luminance = [100.0] * 8
    check(run_dctl(p, PIXELS) == PIXELS, "Amount = 0 must be a bit exact bypass")

    # bypass checkbox
    p.amount = 100.0
    p.bypass = True
    check(run_dctl(p, PIXELS) == PIXELS, "Bypass must be a bit exact bypass")

    # amount cross-fade is a true blend of input and full-strength output
    p = params(global_saturation=80.0)
    full = run_dctl(p, PIXELS)
    p.amount = 40.0
    partial = run_dctl(p, PIXELS)
    worst = 0.0
    for src, mixed, done in zip(PIXELS, partial, full):
        for a, b, c in zip(src, mixed, done):
            worst = max(worst, abs(b - (a + (c - a) * 0.4)))
    check(worst < 1e-6, "Amount must linearly cross-fade input and processed (error %.3g)" % worst)

    # a region slider must not disturb pixels outside its influence
    p = params()
    p.set_region("blue", hue=100.0, sat=100.0, lum=100.0)
    reds = [hsv_to_rgb(h, s, v) for h in (0.0, 10.0, 20.0) for s in (0.4, 0.9) for v in (0.3, 0.8)]
    check(run_dctl(p, reds) == reds,
          "a blue-only adjustment must leave red pixels bit exactly unchanged")


# ===========================================================================
# 4. the 24 per-colour controls, one at a time
# ===========================================================================
def test_individual_controls():
    section("24 individual HSL controls")

    neutrals = f32px([(0.0, 0.0, 0.0), (0.25, 0.25, 0.25), (0.5, 0.5, 0.5),
                      (0.75, 0.75, 0.75), (1.0, 1.0, 1.0)])

    for i, name in enumerate(REGION_NAMES):
        centre = REGION_CENTRES[i]
        target = hsv_to_rgb(centre, 0.8, 0.75)
        far = hsv_to_rgb((centre + 180.0) % 360.0, 0.8, 0.75)
        probes = [target, far] + neutrals

        # ---- hue -------------------------------------------------------
        for direction in (+100.0, -100.0):
            p = params()
            p.set_region(name, hue=direction)
            out = run_dctl(p, probes)
            moved = rgb_to_hue(out[0], max(out[0]), chroma(out[0]))
            expected = (centre + direction / 100.0 * 30.0) % 360.0
            delta = abs((moved - expected + 180.0) % 360.0 - 180.0)
            check(delta < 1.0, "%s hue %+g should reach %.1f deg, reached %.1f"
                  % (name, direction, expected, moved))
            check(out[1] == far, "%s hue %+g must not move the opposite hue" % (name, direction))
            check(out[2:] == neutrals, "%s hue %+g must not move neutrals" % (name, direction))

        # ---- saturation ------------------------------------------------
        p = params()
        p.set_region(name, sat=-100.0)
        out = run_dctl(p, probes)
        check(chroma(out[0]) < 1e-6, "%s saturation -100 must reach a true neutral" % name)
        check(out[1] == far, "%s saturation -100 must not move the opposite hue" % name)
        check(out[2:] == neutrals, "%s saturation -100 must not move neutrals" % name)

        p.set_region(name, sat=100.0)
        out = run_dctl(p, probes)
        check(chroma(out[0]) > chroma(target) * 1.2,
              "%s saturation +100 must clearly increase chroma" % name)
        check(finite(out), "%s saturation +100 produced a non-finite value" % name)
        check(out[2:] == neutrals, "%s saturation +100 must not move neutrals" % name)

        # saturation must be monotonic in the slider
        chromas = []
        for value in (-100.0, -50.0, 0.0, 50.0, 100.0):
            p = params()
            p.set_region(name, sat=value)
            chromas.append(chroma(run_dctl(p, [target])[0]))
        check(all(a < b for a, b in zip(chromas, chromas[1:])),
              "%s saturation must be monotonic, got %s" % (name, ["%.4f" % c for c in chromas]))

        # ---- luminance -------------------------------------------------
        lumas = []
        for value in (-100.0, -50.0, 0.0, 50.0, 100.0):
            p = params()
            p.set_region(name, lum=value)
            out = run_dctl(p, probes)
            lumas.append(luma(out[0]))
            check(out[1] == far, "%s luminance %+g must not move the opposite hue" % (name, value))
            check(out[2:] == neutrals, "%s luminance %+g must not move neutrals" % (name, value))
            # hue and saturation must survive a luminance move
            if value != 0.0:
                h0 = rgb_to_hue(target, max(target), chroma(target))
                h1 = rgb_to_hue(out[0], max(out[0]), chroma(out[0]))
                s0 = saturation_measure(max(target), chroma(target))
                s1 = saturation_measure(max(out[0]), chroma(out[0]))
                check(abs((h1 - h0 + 180.0) % 360.0 - 180.0) < 0.05,
                      "%s luminance %+g shifted hue by %.3f deg" % (name, value, h1 - h0))
                check(abs(s1 - s0) < 2e-3,
                      "%s luminance %+g shifted saturation by %.4f" % (name, value, s1 - s0))
        check(all(a < b for a, b in zip(lumas, lumas[1:])),
              "%s luminance must be monotonic, got %s" % (name, ["%.4f" % v for v in lumas]))


# ===========================================================================
# 5. region weighting
# ===========================================================================
def test_region_weighting():
    section("hue region weighting")

    for falloff in (0.0, 0.25, 0.5, 0.75, 1.0):
        worst = 0.0
        for step in range(0, 36000):
            weights = region_weights(step / 100.0, falloff)
            worst = max(worst, abs(sum(weights) - 1.0))
        check(worst < 1e-9,
              "region weights must sum to 1 at falloff %g (worst error %.3g)" % (falloff, worst))

    for i, centre in enumerate(REGION_CENTRES):
        weights = region_weights(centre, 0.5)
        check(abs(weights[i] - 1.0) < 1e-9,
              "a colour on the %s centre must be owned by %s alone" % (REGION_NAMES[i], REGION_NAMES[i]))

    # exactly two regions may be active, and the split is smooth
    weights = region_weights(45.0, 0.5)
    check(sum(1 for w in weights if w > 0.0) == 2, "at most two regions may overlap")
    check(abs(weights[1] - 0.5) < 1e-9 and abs(weights[2] - 0.5) < 1e-9,
          "the midpoint of an arc must split 50/50")

    # a yellow-orange hue must be shared between orange and yellow
    weights = region_weights(40.0, 0.5)
    check(weights[1] > weights[2] > 0.0,
          "a yellow-orange hue must belong partly to orange and partly to yellow")

    # weights must be continuous in hue at every falloff
    for falloff in (0.0, 0.5, 1.0):
        worst = 0.0
        previous = region_weights(0.0, falloff)
        for step in range(1, 7200):
            current = region_weights(step / 20.0, falloff)
            worst = max(worst, max(abs(a - b) for a, b in zip(current, previous)))
            previous = current
        check(worst < 0.02, "region weights must be continuous at falloff %g (max step %.4f)"
              % (falloff, worst))


# ===========================================================================
# 6. hue continuity of the rendered result
# ===========================================================================
def test_output_continuity():
    """Detect discontinuities by refining the sampling of a hue sweep.

    A large step between neighbouring samples is not by itself a discontinuity -
    an extreme grade legitimately changes quickly.  What separates the two is
    how the largest step behaves when the sweep is sampled four times more
    finely: for a continuous function it shrinks roughly in proportion, for a
    jump it stays put.  Each falloff is swept with alternating extreme settings
    on neighbouring regions, which is the harshest case the control can produce.
    """
    section("output continuity across the hue circle")

    for falloff in (0.0, 50.0, 100.0):
        p = params(hue_falloff=falloff, protect_neutrals=0.0)
        p.hue = [100.0, -100.0] * 4
        p.saturation = [100.0, -100.0] * 4
        p.luminance = [-100.0, 100.0] * 4

        steps = []
        for divisions in (7200, 28800):
            ramp = [hsv_to_rgb(i * 360.0 / divisions, 0.85, 0.8) for i in range(divisions)]
            out = run_dctl(p, ramp)
            check(finite(out), "hue sweep at falloff %g produced a non-finite value" % falloff)
            steps.append(max(max(abs(a - b) for a, b in zip(x, y))
                             for x, y in zip(out, out[1:])))

        ratio = steps[1] / max(steps[0], 1e-12)
        check(ratio < 0.45,
              "hue sweep at falloff %g looks discontinuous: refining the sampling 4x "
              "only reduced the largest step from %.5f to %.5f" % (falloff, steps[0], steps[1]))
        check(steps[0] < 0.05, "hue sweep at falloff %g stepped by %.4f, which is too coarse "
              "for a 0.05 degree step" % (falloff, steps[0]))
        print("  falloff %-5g max step %.5f -> %.5f when sampled 4x finer (ratio %.2f)"
              % (falloff, steps[0], steps[1], ratio))

    # the same check on a saturation ramp: crossing into and out of gamut must
    # not produce a visible edge
    p = params(saturation_protection=100.0, protect_neutrals=0.0)
    p.saturation = [100.0] * 8
    steps = []
    for divisions in (2000, 8000):
        ramp = [hsv_to_rgb(35.0, i / float(divisions - 1), 0.85) for i in range(divisions)]
        out = run_dctl(p, ramp)
        steps.append(max(max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(out, out[1:])))
    check(steps[1] / max(steps[0], 1e-12) < 0.45,
          "saturation ramp looks discontinuous under gamut protection (%.5f -> %.5f)"
          % (steps[0], steps[1]))
    print("  saturation ramp max step %.5f -> %.5f when sampled 4x finer" % (steps[0], steps[1]))


# ===========================================================================
# 7. global saturation, vibrance, neutral protection
# ===========================================================================
def test_global_controls():
    section("global saturation / vibrance / neutral protection")

    neutrals = f32px([(0.0, 0.0, 0.0), (0.5, 0.5, 0.5), (1.0, 1.0, 1.0)])
    colours = [hsv_to_rgb(h, 0.6, 0.7) for h in range(0, 360, 30)]

    check(run_dctl(params(global_saturation=100.0), neutrals) == neutrals,
          "global saturation must not tint neutrals")
    check(run_dctl(params(global_saturation=-100.0), neutrals) == neutrals,
          "global saturation -100 must not disturb neutrals")

    out = run_dctl(params(global_saturation=-100.0), colours)
    check(max(chroma(px) for px in out) < 1e-6, "global saturation -100 must fully desaturate")

    out = run_dctl(params(global_saturation=100.0), colours)
    check(all(chroma(b) > chroma(a) for a, b in zip(colours, out)),
          "global saturation +100 must increase chroma everywhere")

    # global saturation must not shift hue
    worst = 0.0
    for src, dst in zip(colours, out):
        h0 = rgb_to_hue(src, max(src), chroma(src))
        h1 = rgb_to_hue(dst, max(dst), chroma(dst))
        worst = max(worst, abs((h1 - h0 + 180.0) % 360.0 - 180.0))
    check(worst < 0.05, "global saturation shifted hue by %.4f deg" % worst)

    # ---- vibrance ------------------------------------------------------
    weak = hsv_to_rgb(200.0, 0.15, 0.7)
    strong = hsv_to_rgb(200.0, 0.95, 0.7)
    out = run_dctl(params(vibrance=100.0), [weak, strong])
    weak_gain = chroma(out[0]) / chroma(weak)
    strong_gain = chroma(out[1]) / chroma(strong)
    check(weak_gain > strong_gain * 1.5,
          "vibrance must lift weak colours far more than saturated ones (%.3f vs %.3f)"
          % (weak_gain, strong_gain))

    skin = hsv_to_rgb(32.0, 0.45, 0.8)
    other = hsv_to_rgb(212.0, 0.45, 0.8)
    out = run_dctl(params(vibrance=100.0), [skin, other])
    skin_gain = chroma(out[0]) / chroma(skin)
    other_gain = chroma(out[1]) / chroma(other)
    check(skin_gain < other_gain,
          "vibrance must hold back over skin hues (%.3f vs %.3f)" % (skin_gain, other_gain))

    sat_out = run_dctl(params(global_saturation=100.0), [weak, strong])
    check(chroma(out[1]) < chroma(sat_out[1]),
          "vibrance must not simply alias global saturation")

    out = run_dctl(params(vibrance=-100.0), [weak, strong])
    check(chroma(out[0]) < chroma(weak) and chroma(out[1]) < chroma(strong),
          "negative vibrance must reduce chroma")
    check(chroma(out[1]) / chroma(strong) > chroma(out[0]) / chroma(weak),
          "negative vibrance must keep more of the strongest colours")
    check(run_dctl(params(vibrance=100.0), neutrals) == neutrals,
          "vibrance must not tint neutrals")

    # ---- protect neutrals ----------------------------------------------
    faint = hsv_to_rgb(30.0, 0.06, 0.6)
    p_off = params(protect_neutrals=0.0)
    p_off.set_region("orange", lum=100.0, sat=100.0)
    p_on = params(protect_neutrals=100.0)
    p_on.set_region("orange", lum=100.0, sat=100.0)
    moved_off = max(abs(a - b) for a, b in zip(faint, run_dctl(p_off, [faint])[0]))
    moved_on = max(abs(a - b) for a, b in zip(faint, run_dctl(p_on, [faint])[0]))
    check(moved_on < moved_off * 0.35,
          "Protect Neutrals must strongly reduce the move on a near-neutral pixel (%.4f vs %.4f)"
          % (moved_on, moved_off))

    for protect in (0.0, 50.0, 100.0):
        p = params(protect_neutrals=protect)
        p.hue = [100.0] * 8
        p.saturation = [100.0] * 8
        p.luminance = [100.0] * 8
        check(run_dctl(p, neutrals) == neutrals,
              "exact neutrals must never move, even at Protect Neutrals = %g" % protect)


# ===========================================================================
# 8. gamut behaviour and numerical stability
# ===========================================================================
def test_stability():
    section("gamut and numerical stability")

    extremes = []
    for hue in (0.0, 100.0, -100.0):
        for sat in (0.0, 100.0, -100.0):
            for lum in (0.0, 100.0, -100.0):
                p = params()
                p.hue = [hue] * 8
                p.saturation = [sat] * 8
                p.luminance = [lum] * 8
                extremes.append(("h%+g s%+g l%+g" % (hue, sat, lum), p))

    for label, p in extremes:
        for falloff in (0.0, 100.0):
            for protect in (0.0, 100.0):
                p.hue_falloff = falloff
                p.saturation_protection = protect
                out = run_dctl(p, PIXELS)
                check(finite(out), "%s (falloff %g, protection %g) produced NaN or infinity"
                      % (label, falloff, protect))
                bound = max(abs(v) for px in out for v in px)
                check(bound < 1e4, "%s produced an unbounded value (%.3g)" % (label, bound))

    for value in (100.0, -100.0):
        for name in ("global_saturation", "vibrance"):
            p = params(**{name: value})
            out = run_dctl(p, PIXELS)
            check(finite(out), "%s = %g produced NaN or infinity" % (name, value))

    # saturation protection must remove negative excursions it created
    p = params(saturation_protection=100.0, protect_neutrals=0.0)
    p.saturation = [100.0] * 8
    p.global_saturation = 100.0
    in_gamut = [px for px in PIXELS if min(px) >= 0.0]
    out = run_dctl(p, in_gamut)
    worst = min(min(px) for px in out)
    check(worst > -1e-5,      # float32 rounding of a value that solves to exactly 0
          "Saturation Protection = 100 must not leave negative channels (worst %.4g)" % worst)

    # ... and it must be optional
    p.saturation_protection = 0.0
    loose = run_dctl(p, in_gamut)
    check(min(min(px) for px in loose) < worst,
          "Saturation Protection = 0 should allow wider excursions than 100")

    # display-mode luminance must not push highlights out of the display range
    p = params(protect_neutrals=0.0)
    p.luminance = [100.0] * 8
    bright = [hsv_to_rgb(h, s, 1.0) for h in range(0, 360, 15) for s in (0.2, 0.6, 1.0)]
    out = run_dctl(p, bright)
    check(max(max(px) for px in out) <= 1.0 + 1e-6,
          "display-mode Luminance +100 must keep white at white")

    # every extreme combination on a hostile pixel set stays finite
    hostile = f32px([(0.0, 0.0, 0.0), (1e-30, 0.0, 0.0), (-1e-30, 1e-30, 0.0),
                     (1e6, 1e6, 1e6), (1e-6, -1e-6, 1e-6), (1.0, 1.0, 1.0),
                     (0.0, 1e-7, 0.0), (-5.0, 5.0, 0.0)])
    p = params(protect_neutrals=0.0, hue_falloff=0.0, preserve_luminance=100.0,
                    saturation_protection=100.0, global_saturation=100.0, vibrance=100.0)
    p.hue = [100.0] * 8
    p.saturation = [100.0] * 8
    p.luminance = [100.0] * 8
    for encoding in (ENC_DISPLAY, ENC_LOG, ENC_LINEAR, ENC_DWG):
        p.encoding = encoding
        out = run_dctl(p, hostile)
        check(finite(out), "hostile pixels produced NaN or infinity in encoding %d" % encoding)


# ===========================================================================
# 9. encodings
# ===========================================================================
def test_encodings():
    section("input encodings")

    # DaVinci Intermediate round trip
    worst = 0.0
    from color_mixer_reference import di_encode, di_decode
    for i in range(0, 2001):
        x = -0.05 + i * 0.02
        worst = max(worst, abs(di_decode(di_encode(x)) - x) / max(abs(x), 1e-3))
    check(worst < 1e-6, "DaVinci Intermediate encode/decode must round trip (%.3g)" % worst)

    # log-mode luminance is an exposure offset of one stop at +/-100
    p = params(encoding=ENC_LOG, protect_neutrals=0.0)
    p.set_region("blue", lum=100.0)
    src = [hsv_to_rgb(240.0, 0.5, 0.6)]        # exactly on the blue centre
    out = run_dctl(p, src)
    offset = out[0][2] - src[0][2]
    check(abs(offset - 0.07329248) < 1e-4,
          "log-mode Luminance +100 should offset by one stop, offset was %.6f" % offset)

    # linear mode: a luminance move must be a clean exposure scale
    p = params(encoding=ENC_LINEAR, protect_neutrals=0.0, preserve_luminance=0.0)
    p.set_region("blue", lum=100.0)
    src = [hsv_to_rgb(240.0, 0.8, 0.30)]       # exactly on the blue centre
    out = run_dctl(p, src)
    ratios = [b / a for a, b in zip(src[0], out[0])]
    check(max(ratios) - min(ratios) < 2e-3,
          "linear-mode Luminance must scale all channels equally, ratios %s"
          % ["%.4f" % r for r in ratios])
    check(abs(ratios[0] - 2.0) < 0.05,
          "linear-mode Luminance +100 should be about one stop, was %.3f x" % ratios[0])

    # hue selection in linear mode must use the perceptual hue, not the linear one
    warm_linear = f32px([(0.30, 0.12, 0.03)])[0]
    p = params(encoding=ENC_LINEAR, protect_neutrals=0.0)
    p.set_region("orange", sat=-100.0)
    out = run_dctl(p, [warm_linear])
    check(chroma(out[0]) < chroma(warm_linear) * 0.5,
          "a warm linear pixel must be picked up by the orange region")


# ===========================================================================
# 9b. DaVinci Wide Gamut mode
# ===========================================================================
def dctl_region_weights(encoding, pixel):
    """The DCTL's own region weights for a pixel, read out through the mask preview."""
    weights = []
    for region in range(8):
        p = params(encoding=encoding, preview=PV_MASK, preview_region=region)
        weights.append(run_dctl(p, [pixel])[0][0])
    return weights


def test_davinci_wide_gamut():
    section("DaVinci Wide Gamut mode")

    # the matrix in the DCTL must invert the independently derived forward one
    product = _matmul(list(DWG_TO_REC709), REC709_TO_DWG)
    worst = max(abs(product[i][j] - (1.0 if i == j else 0.0))
                for i in range(3) for j in range(3))
    check(worst < 5e-4,
          "the DCTL's DaVinci WG -> Rec.709 matrix must invert a matrix derived "
          "independently from the published chromaticities (worst %.2e)" % worst)
    for i, row in enumerate(DWG_TO_REC709):
        check(abs(sum(row) - 1.0) < 1e-7,
              "matrix row %d must sum to 1 so that a neutral maps to a neutral" % i)

    # ---- the headline claim -------------------------------------------------
    # A colour we know in Rec.709 terms, carried into DaVinci WG by CST IN, must
    # still be selected by the region its Rec.709 appearance belongs to.
    worst_corrected = 0.0
    worst_uncorrected = 0.0
    for name, rec709 in DWG_REFERENCE:
        expected = region_weights(rgb_to_hue(rec709, max(rec709), chroma(rec709)), 50.0 * 0.01)
        wire = rec709_display_to_dwg_di(rec709)

        corrected = dctl_region_weights(ENC_DWG, wire)
        uncorrected = dctl_region_weights(ENC_LOG, wire)

        error = max(abs(a - b) for a, b in zip(corrected, expected))
        worst_corrected = max(worst_corrected, error)
        worst_uncorrected = max(worst_uncorrected,
                                max(abs(a - b) for a, b in zip(uncorrected, expected)))
        check(error < 0.02,
              "%s: DaVinci WG mode should select the same regions as its Rec.709 "
              "appearance, worst weight error %.3f" % (name, error))

    print("  worst region-weight error vs the Rec.709 appearance:")
    print("    DaVinci WG mode   %.4f" % worst_corrected)
    print("    reading DWG raw   %.4f  (what Log direct would do)" % worst_uncorrected)
    check(worst_uncorrected > 10.0 * worst_corrected,
          "the correction must make a real difference; reading DaVinci WG directly was "
          "only off by %.4f" % worst_uncorrected)

    # the worst case is foliage, which is the reason the mode exists
    foliage = rec709_display_to_dwg_di((0.259, 0.400, 0.196))
    green_corrected = dctl_region_weights(ENC_DWG, foliage)[3]
    green_raw = dctl_region_weights(ENC_LOG, foliage)[3]
    check(green_corrected > 0.85 > green_raw,
          "a green leaf must land in the Green region (corrected %.2f, raw %.2f)"
          % (green_corrected, green_raw))
    print("  green leaf, Green region weight: %.2f corrected, %.2f raw" %
          (green_corrected, green_raw))

    # ---- neutrals -----------------------------------------------------------
    neutrals = f32px([(0.0, 0.0, 0.0), (0.09, 0.09, 0.09), (0.5, 0.5, 0.5),
                      (0.95, 0.95, 0.95)])
    p = params(encoding=ENC_DWG, protect_neutrals=0.0)
    p.hue = [100.0] * 8
    p.saturation = [100.0] * 8
    p.luminance = [100.0] * 8
    check(run_dctl(p, neutrals) == neutrals,
          "neutrals must not move in DaVinci WG mode, at any setting")

    # ---- luminance is still a one-stop code offset --------------------------
    p = params(encoding=ENC_DWG, protect_neutrals=0.0)
    p.set_region("blue", lum=100.0)
    source = [rec709_display_to_dwg_di(hsv_to_rgb(240.0, 0.6, 0.5))]
    out = run_dctl(p, source)
    offsets = [b - a for a, b in zip(source[0], out[0])]
    check(max(offsets) - min(offsets) < 1e-5,
          "DaVinci WG Luminance must offset all three channels equally, got %s"
          % ["%.5f" % o for o in offsets])
    check(abs(offsets[0] - 0.07329248) < 2e-3,
          "DaVinci WG Luminance +100 should be one stop, was %.6f" % offsets[0])

    # ---- continuity ---------------------------------------------------------
    p = params(encoding=ENC_DWG, protect_neutrals=0.0)
    p.hue = [100.0, -100.0] * 4
    p.saturation = [100.0, -100.0] * 4
    p.luminance = [-100.0, 100.0] * 4
    steps = []
    for divisions in (3600, 14400):
        ramp = [rec709_display_to_dwg_di(hsv_to_rgb(i * 360.0 / divisions, 0.9, 0.75))
                for i in range(divisions)]
        out = run_dctl(p, ramp)
        check(finite(out), "DaVinci WG hue sweep produced a non-finite value")
        steps.append(max(max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(out, out[1:])))
    check(steps[1] / max(steps[0], 1e-12) < 0.45,
          "the DaVinci WG selection hue looks discontinuous (%.5f -> %.5f)"
          % (steps[0], steps[1]))
    print("  hue sweep max step %.5f -> %.5f when sampled 4x finer" % (steps[0], steps[1]))


# ===========================================================================
# 10. colour range preview
# ===========================================================================
def test_preview():
    section("colour range preview")

    p = params(preview=PV_MASK, preview_region=1)
    probes = [hsv_to_rgb(30.0, 0.8, 0.7), hsv_to_rgb(210.0, 0.8, 0.7)]
    out = run_dctl(p, probes)
    check(abs(out[0][0] - 1.0) < 1e-6 and out[0][0] == out[0][1] == out[0][2],
          "the mask must read 1 on the orange centre")
    check(out[1] == (0.0, 0.0, 0.0), "the mask must read 0 well outside the region")

    p = params(preview=PV_ISOLATE, preview_region=5)
    probes = [hsv_to_rgb(240.0, 0.8, 0.7), hsv_to_rgb(60.0, 0.8, 0.7)]
    out = run_dctl(p, probes)
    check(chroma(out[0]) > 0.3, "isolate must keep the selected region in colour")
    check(chroma(out[1]) < 1e-6, "isolate must desaturate everything else")


# ===========================================================================
def main():
    if not os.path.exists(HARNESS):
        print("building harness...")
        subprocess.run([os.path.join(HERE, "build.sh")], check=True)

    test_static_source()
    test_cross_validation()
    test_identity()
    test_individual_controls()
    test_region_weighting()
    test_output_continuity()
    test_global_controls()
    test_stability()
    test_encodings()
    test_davinci_wide_gamut()
    test_preview()

    print("\n" + "=" * 60)
    if _failures:
        print("%d of %d checks FAILED" % (len(_failures), _tests_run))
        for message in _failures:
            print("  - " + message)
        return 1
    print("all %d checks passed" % _tests_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
