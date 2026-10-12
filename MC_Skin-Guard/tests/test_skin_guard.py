#!/usr/bin/env python3
"""Test suite for MC_Skin-Guard-v1.0.dctl.

MarkCaptures MC Skin Guard - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Two implementations are tested against each other and against the
requirements:

  * the real .dctl, compiled on the host through sg_shim.h (tests/build.sh)
    and run by tests/sg_harness - this is what the bit-exact checks use,
  * skin_guard_reference.py, the Python mirror of the same maths.

Covered:
  1. static checks of the DCTL source (header / footer, one-line entry point,
     a tooltip for every control, allowed intrinsics only, combo enums),
  2. DCTL == Python reference, every encoding, random settings, incl. Evenness,
  3. identity (all effects at 0), Bypass and Amount 0 are bit exact,
  4. neutral greys are untouched (bit exact) at extreme settings,
  5. hue sweeps: no folds, no jumps, every encoding, extreme settings,
  6. saturation and luma sweeps: no folds at the qualifier edges,
  7. skin patches: Hue Consolidate, Redness, Yellow Green, Protect Skin,
     Skin Saturation, Density and Exposure do what they say,
  8. Evenness: colour variance down, luma detail kept, no bleeding,
  9. extreme slider values: finite, in range,
 10. Show Skin Mask and Overall Amount.

Run with:  python3 tests/test_skin_guard.py      (needs g++ / gcc and numpy)
"""

from __future__ import annotations

import itertools
import math
import os
import random
import re
import struct
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import skin_guard_reference as ref  # noqa: E402
from skin_guard_reference import (  # noqa: E402
    ENC_DISPLAY, ENC_LOG, ENC_LINEAR, ENC_DWG, ENC_ACESCCT, ENC_CINEON, ENCODINGS,
    ENCODING_NAMES, SM_MASK, SM_ISOLATE, SkinGuardParams,
)

DCTL_PATH = os.path.join(ROOT, "MC_Skin-Guard-v1.0.dctl")
HARNESS = os.path.join(HERE, "sg_harness")

_failures = []
_checks = 0


def check(condition, message):
    global _checks
    _checks += 1
    if not condition:
        _failures.append(message)
    print(("  ok    " if condition else "  FAIL  ") + message)
    return bool(condition)


def section(title):
    print("\n=== %s ===" % title)


# ---------------------------------------------------------------------------
#  float32, encodings for building test input
# ---------------------------------------------------------------------------
def f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def f32px(px):
    return tuple(f32(v) for v in px)


def srgb_decode(v):
    if v <= 0.0:
        return v / 12.92
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


acescct_encode = ref.acescct_encode
cineon_encode = ref.cineon_encode


REC709_TO_DWG = np.linalg.inv(np.array(ref.DWG_TO_REC709))
REC709_TO_AP1 = np.linalg.inv(np.array(ref.AP1_TO_REC709))


def from_display(rgb709, encoding):
    """Express a Rec.709 display colour in the given input encoding."""
    lin = [srgb_decode(v) for v in rgb709]
    if encoding == ENC_DISPLAY:
        out = rgb709
    elif encoding == ENC_LOG:
        out = [ref.di_encode(v) for v in lin]
    elif encoding == ENC_LINEAR:
        out = lin
    elif encoding == ENC_DWG:
        out = [ref.di_encode(v) for v in REC709_TO_DWG @ np.array(lin)]
    elif encoding == ENC_ACESCCT:
        out = [acescct_encode(v) for v in REC709_TO_AP1 @ np.array(lin)]
    else:
        out = [cineon_encode(v) for v in lin]
    return f32px(float(v) for v in out)


def hsv(h, s, v):
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs(math.fmod(h / 60.0, 2.0) - 1.0))
    m = v - c
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60.0) % 6]
    return (r + m, g + m, b + m)


def sel_measure(rgb, encoding):
    """(hue, sat, luma) of an INPUT-encoded pixel, in the selection encoding."""
    return ref.measure(ref.to_working(rgb, encoding), encoding)


def unwrap(hues):
    out = [hues[0]]
    for h in hues[1:]:
        out.append(out[-1] + ref.hue_delta(h, out[-1] % 360.0))
    return out


# ---------------------------------------------------------------------------
#  running the compiled DCTL
# ---------------------------------------------------------------------------
def run_dctl(p: SkinGuardParams, pixels, width=None, height=None):
    if width is None:
        width, height = len(pixels), 1
    payload = ["%d %d" % (width, height)]
    payload += ["%s %s %s" % (float(a).hex(), float(b).hex(), float(c).hex()) for a, b, c in pixels]
    res = subprocess.run([HARNESS] + p.to_dctl_args(), input="\n".join(payload) + "\n",
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("harness failed: " + res.stderr)
    return [tuple(float.fromhex(t) for t in line.split()) for line in res.stdout.splitlines() if line.strip()]


def run_dctl_pixels(p, pixels):
    """Independent pixels: each one is its own 1x1 frame (no neighbours)."""
    # A 1-pixel-high frame would let Evenness see horizontal neighbours, so
    # pixel tests that must be independent run with Evenness off or use this.
    out = []
    for px in pixels:
        out += run_dctl(p, [px], 1, 1)
    return out


def bits(px):
    return tuple(struct.pack("<f", v) for v in px)


def finite(px):
    return all(math.isfinite(v) for v in px)


EXTREME_SETTINGS = [
    dict(consolidate=100, redness=100, yellow_green=100),
    dict(protect=100, protect_width=90, natural_sat=90),
    dict(protect=100, natural_sat=5),
    dict(skin_sat=100, density=100, exposure=100),
    dict(skin_sat=-100, density=-100, exposure=-100),
    dict(consolidate=100, protect=100, skin_sat=100, density=-100, exposure=100, evenness=100),
    dict(consolidate=100, redness=-100, yellow_green=100, protect=50, skin_sat=-100,
         density=100, exposure=-100, evenness=100, softness=0, hue_width=4,
         sat_low=40, sat_high=45, luma_low=40, luma_high=45),
    dict(consolidate=100, protect=100, skin_sat=100, exposure=100, softness=100,
         hue_width=120, sat_low=0, sat_high=100),
]


# ---------------------------------------------------------------------------
#  1. static checks
# ---------------------------------------------------------------------------
def test_static():
    section("1. static checks of the DCTL source")
    src = open(DCTL_PATH, encoding="utf-8").read()
    lines = src.split("\n")
    banner = ["// MarkCaptures MC Skin Guard",
              "// © 2026 Mark van der Vis / MarkCaptures",
              "// www.markcaptures.com"]
    check(lines[:3] == banner, "file starts with the MarkCaptures banner")
    tail = [l for l in lines if l.strip()][-3:]
    check(tail == banner, "file ends with the MarkCaptures banner")
    check("MIT" not in src, "no MIT licence text")
    check("All rights reserved" in src, "all-rights-reserved licence present")

    entry = [l for l in lines if re.match(r"\s*__DEVICE__\s+float3\s+transform\s*\(", l)]
    check(len(entry) == 1 and entry[0].strip() ==
          "__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, "
          "__TEXTURE__ p_TexR, __TEXTURE__ p_TexG, __TEXTURE__ p_TexB)",
          "texture transform() declaration is on one line, exactly as Resolve expects")

    params = re.findall(r"^DEFINE_UI_PARAMS\((\w+),\s*([^,]+),\s*(\w+)", src, re.M)
    tips = set(re.findall(r"^DEFINE_UI_TOOLTIP\((\w+),\s*\"[^\"]+\"\)", src, re.M))
    names = [p[0] for p in params]
    check(len(names) == len(set(names)), "UI parameter names are unique")
    missing = [n for n in names if n not in tips]
    check(not missing, "every control has a DEFINE_UI_TOOLTIP (missing: %s)" % missing)
    allowed = {"DCTLUI_SLIDER_FLOAT", "DCTLUI_SLIDER_INT", "DCTLUI_VALUE_BOX",
               "DCTLUI_CHECK_BOX", "DCTLUI_COMBO_BOX", "DCTLUI_COLOR_PICKER"}
    check(all(p[2] in allowed for p in params), "only supported UI types are used")
    labels = [p[1].strip() for p in params]
    check(all(re.match(r"^[A-Za-z0-9 ]+$", l) for l in labels),
          "UI labels use only letters, digits and spaces")

    code = re.sub(r"//.*", "", src)
    check("_exp10f" not in code, "_exp10f is not used")
    intrinsics = set(re.findall(r"\b(_[a-z][a-z0-9]*)\s*\(", code))
    ok = {"_fmaxf", "_fminf", "_clampf", "_saturatef", "_fabs", "_fmod", "_powf", "_expf",
          "_exp2f", "_logf", "_log2f", "_floor", "_cosf", "_sinf", "_tex2D"}
    check(intrinsics <= ok, "only standard DCTL intrinsics are used (extra: %s)" % (intrinsics - ok))
    check("#include" not in code, "DCTL is self-contained (no #include)")
    check(not re.search(r"\bdouble\b", code), "no double precision")

    shim = open(os.path.join(HERE, "sg_shim.h")).read()
    for var, enum_line in (("uiEncoding", "ENC_DISPLAY = 0, ENC_LOG = 1, ENC_LINEAR = 2, ENC_DWG = 3, "
                                          "ENC_ACESCCT = 4, ENC_CINEON = 5"),
                           ("uiShowMask", "SM_OFF = 0, SM_MASK = 1, SM_ISOLATE = 2")):
        m = re.search(r"DEFINE_UI_PARAMS\(%s,[^{]*\{([^}]*)\}" % var, src)
        declared = ", ".join("%s = %d" % (n.strip(), i) for i, n in enumerate(m.group(1).split(",")))
        check(declared == enum_line and enum_line in shim, "%s enum matches the test shim" % var)
    m = re.search(r"DEFINE_UI_PARAMS\(uiEncoding,[^}]*\},\s*\{([^}]*)\}", src)
    check([s.strip() for s in m.group(1).split(",")] ==
          [ENCODING_NAMES[e] for e in ENCODINGS], "Input Encoding names match the MC HSL Editor")

    # Resolve lists sliders, then check boxes, then combos; keep the file in
    # that order too so it reads like the UI.
    kinds = [p[2] for p in params]
    order = {"DCTLUI_SLIDER_FLOAT": 0, "DCTLUI_CHECK_BOX": 1, "DCTLUI_COMBO_BOX": 2}
    check(kinds == sorted(kinds, key=lambda k: order[k]), "declarations follow Resolve's UI order")


# ---------------------------------------------------------------------------
#  2. DCTL == reference
# ---------------------------------------------------------------------------
def random_params(rng, encoding):
    p = SkinGuardParams(encoding=encoding)
    p.hue_centre = rng.uniform(15, 40)
    p.hue_width = rng.uniform(10, 60)
    p.sat_low = rng.uniform(0, 30)
    p.sat_high = rng.uniform(40, 100)
    p.luma_low = rng.uniform(0, 30)
    p.luma_high = rng.uniform(60, 100)
    p.softness = rng.uniform(0, 100)
    for name in ("consolidate", "protect", "evenness"):
        setattr(p, name, rng.choice([0.0, rng.uniform(0, 100), 100.0]))
    for name in ("redness", "yellow_green", "skin_sat", "density", "exposure"):
        setattr(p, name, rng.choice([0.0, rng.uniform(-100, 100), 100.0, -100.0]))
    p.protect_width = rng.uniform(0, 90)
    p.natural_sat = rng.uniform(5, 90)
    p.even_radius = rng.uniform(1, 6)
    p.amount = rng.choice([100.0, rng.uniform(0, 100)])
    return p


def skin_like(rng):
    return hsv(rng.uniform(-10, 70), rng.uniform(0.0, 0.9), rng.uniform(0.05, 1.0))


def test_cross_validation():
    section("2. compiled DCTL agrees with the Python reference")
    rng = random.Random(1)
    worst_all = 0.0
    for encoding in ENCODINGS:
        worst = 0.0
        for trial in range(12):
            p = random_params(rng, encoding)
            w, h = 12, 8
            frame = [from_display(skin_like(rng) if rng.random() < 0.8 else
                                  (rng.random(), rng.random(), rng.random()), encoding)
                     for _ in range(w * h)]
            a = run_dctl(p, frame, w, h)
            b = ref.process_frame(frame, w, h, p)
            worst = max(worst, max(max(abs(x - y) for x, y in zip(pa, pb)) for pa, pb in zip(a, b)))
        worst_all = max(worst_all, worst)
        check(worst < 2e-4, "%-24s max |DCTL - reference| = %.2e" % (ENCODING_NAMES[encoding], worst))
    print("  worst difference over all encodings: %.2e" % worst_all)

    # the selection round trip used by the hue / saturation operators is exact
    # and clips nothing, including values far outside Rec.709
    rng = random.Random(11)
    for encoding in (ENC_LINEAR, ENC_DWG, ENC_ACESCCT, ENC_CINEON):
        worst = 0.0
        for _ in range(3000):
            w = tuple(rng.uniform(-0.02, 0.75) for _ in range(3))     # up to ~10x linear white
            back = ref.selection_to_working(ref.selection_rgb(w, encoding), encoding)
            worst = max(worst, max(abs(a - b) for a, b in zip(w, back)))
        check(worst < 1e-6, "%s: selection round trip is exact (%.1e)" % (ENCODING_NAMES[encoding], worst))
    # a wide-gamut orange outside Rec.709 keeps its out-of-gamut component
    # a skin-like orange just outside Rec.709 (negative blue), in DaVinci WG
    wide = f32px(ref.di_encode(v) for v in REC709_TO_DWG @ np.array([0.55, 0.22, -0.02]))
    lin709 = np.array(ref.DWG_TO_REC709) @ np.array([ref.di_decode(v) for v in wide])
    out = run_dctl(SkinGuardParams(encoding=ENC_DWG, consolidate=60, sat_high=100), [wide])[0]
    lin_out = np.array(ref.DWG_TO_REC709) @ np.array([ref.di_decode(v) for v in out])
    check(lin709.min() < 0 and lin_out.min() < 0 and max(abs(a - b) for a, b in zip(out, wide)) > 1e-4,
          "DaVinci WG: colour outside Rec.709 is processed and stays outside (min %.4f -> %.4f)" %
          (lin709.min(), lin_out.min()))


# ---------------------------------------------------------------------------
#  3. identity / bypass / amount 0
# ---------------------------------------------------------------------------
def awkward_pixels(rng, n=300):
    px = [(rng.uniform(-0.2, 1.5), rng.uniform(-0.2, 1.5), rng.uniform(-0.2, 1.5)) for _ in range(n)]
    px += [skin_like(rng) for _ in range(n)]
    px += [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1e-8, 0.0, 0.0), (8.0, 4.0, 2.0), (-1.0, 0.5, 2.0)]
    return [f32px(p) for p in px]


def test_identity():
    section("3. identity, Bypass and Amount 0 are bit exact")
    rng = random.Random(2)
    pixels = awkward_pixels(rng)
    for encoding in ENCODINGS:
        name = ENCODING_NAMES[encoding]
        # effects at zero, qualifier moved around: still the identity
        for p in (SkinGuardParams(encoding=encoding),
                  SkinGuardParams(encoding=encoding, hue_centre=40, hue_width=90, sat_low=0,
                                  softness=100, protect_width=90, natural_sat=90, even_radius=32)):
            out = run_dctl(p, pixels)
            check(all(bits(a) == bits(b) for a, b in zip(out, pixels)), "%s: identity bit exact" % name)
        loud = dict(EXTREME_SETTINGS[5])
        out = run_dctl(SkinGuardParams(encoding=encoding, bypass=1, **loud), pixels)
        check(all(bits(a) == bits(b) for a, b in zip(out, pixels)), "%s: Bypass bit exact" % name)
        out = run_dctl(SkinGuardParams(encoding=encoding, amount=0, **loud), pixels)
        check(all(bits(a) == bits(b) for a, b in zip(out, pixels)), "%s: Amount 0 bit exact" % name)
        # Redness / Yellow Green pushed below zero without Consolidate: no pull
        out = run_dctl(SkinGuardParams(encoding=encoding, redness=-100, yellow_green=-60), pixels)
        check(all(bits(a) == bits(b) for a, b in zip(out, pixels)),
              "%s: negative side controls alone change nothing" % name)


# ---------------------------------------------------------------------------
#  4. greys
# ---------------------------------------------------------------------------
def test_neutrals():
    section("4. neutral greys are never touched (bit exact)")
    levels = [f32(v) for v in np.concatenate([np.linspace(-0.1, 1.2, 140), [0.0, 0.18, 0.5, 1.0, 4.0]])]
    greys = [(v, v, v) for v in levels]
    for encoding in ENCODINGS:
        bad = 0
        for s in EXTREME_SETTINGS:
            p = SkinGuardParams(encoding=encoding, **s)
            p.sat_low = 0.0           # widest possible saturation range
            # a 2-D frame so Evenness has grey neighbours to read
            out = run_dctl(p, greys, len(greys) // 5, 5) if len(greys) % 5 == 0 else run_dctl(p, greys)
            bad += sum(bits(a) != bits(b) for a, b in zip(out, greys))
        check(bad == 0, "%s: greys untouched under %d extreme settings" % (ENCODING_NAMES[encoding],
                                                                            len(EXTREME_SETTINGS)))
        # neutral pixels in the mask preview are black
        out = run_dctl(SkinGuardParams(encoding=encoding, show_mask=SM_MASK, sat_low=0.0), greys)
        check(all(o == (0.0, 0.0, 0.0) for o in out), "%s: greys are 0 in the skin mask" % ENCODING_NAMES[encoding])


# ---------------------------------------------------------------------------
#  5. hue sweeps
# ---------------------------------------------------------------------------
def test_hue_sweeps():
    section("5. hue sweeps: no folds, no jumps")
    step = 0.05
    hues = np.arange(0.0, 360.0, step)
    for encoding in ENCODINGS:
        worst_back = 0.0
        worst_gain = 0.0
        for s, (sat, val) in itertools.product(EXTREME_SETTINGS, [(0.25, 0.8), (0.5, 0.6), (0.85, 0.95)]):
            settings = dict(s)
            settings["evenness"] = 0.0            # pixels are independent here
            p = SkinGuardParams(encoding=encoding, **settings)
            pixels = [from_display(hsv(h, sat, val), encoding) for h in hues]
            out = run_dctl(p, pixels)
            hin = unwrap([sel_measure(px, encoding)[0] for px in pixels])
            hout = unwrap([sel_measure(px, encoding)[0] for px in out])
            din = np.diff(hin)
            dout = np.diff(hout)
            worst_back = max(worst_back, float(-dout.min()))
            worst_gain = max(worst_gain, float((dout / np.maximum(din, 1e-9)).max()))
        check(worst_back < 1e-4, "%-24s hue order kept (largest step backwards %.1e deg)" %
              (ENCODING_NAMES[encoding], worst_back))
        check(worst_gain < 10.0, "%-24s no jumps (largest local hue stretch x%.2f)" %
              (ENCODING_NAMES[encoding], worst_gain))


# ---------------------------------------------------------------------------
#  6. saturation and luma sweeps
# ---------------------------------------------------------------------------
def test_sat_luma_sweeps():
    section("6. saturation and luma sweeps: no folds at the qualifier edges")
    sat_settings = [dict(skin_sat=100), dict(skin_sat=-100), dict(protect=100, natural_sat=90),
                    dict(protect=100, natural_sat=5), dict(protect=100, skin_sat=-100),
                    dict(protect=100, skin_sat=100, natural_sat=50),
                    dict(skin_sat=-100, sat_low=30, sat_high=40, softness=0),
                    dict(skin_sat=100, sat_low=30, sat_high=40, softness=0),
                    dict(protect=100, skin_sat=-100, sat_low=30, sat_high=40, softness=0)]
    luma_settings = [dict(exposure=100), dict(exposure=-100), dict(density=100), dict(density=-100),
                     dict(exposure=100, density=-100, luma_low=40, luma_high=50, softness=0),
                     dict(exposure=-100, density=100, luma_low=40, luma_high=50, softness=0),
                     dict(exposure=100, luma_low=20, luma_high=30, softness=0),
                     dict(exposure=-100, luma_low=70, luma_high=80, softness=0)]
    sats = np.linspace(0.0, 0.98, 1200)
    vals = np.linspace(0.02, 1.0, 1200)
    for encoding in ENCODINGS:
        worst = 0.0
        for s, hue in itertools.product(sat_settings, (15.0, 27.0, 40.0)):
            p = SkinGuardParams(encoding=encoding, **s)
            pixels = [from_display(hsv(hue, x, 0.75), encoding) for x in sats]
            out = run_dctl(p, pixels)
            sin = [sel_measure(px, encoding)[1] for px in pixels]
            sout = [sel_measure(px, encoding)[1] for px in out]
            # only judge the part of the sweep that is in gamut on input
            d = [b - a for a, b, x in zip(sout, sout[1:], sin[1:]) if x < 0.98]
            worst = max(worst, -min(d))
        check(worst < 1e-6, "%-24s saturation order kept (largest step back %.1e)" %
              (ENCODING_NAMES[encoding], worst))
        worst = 0.0
        for s, (hue, sat) in itertools.product(luma_settings, ((27.0, 0.4), (20.0, 0.7))):
            p = SkinGuardParams(encoding=encoding, **s)
            pixels = [from_display(hsv(hue, sat, v), encoding) for v in vals]
            out = run_dctl(p, pixels)
            lout = [sel_measure(px, encoding)[2] for px in out]
            worst = max(worst, -min(b - a for a, b in zip(lout, lout[1:])))
        check(worst < 1e-6, "%-24s luma order kept (largest step back %.1e)" %
              (ENCODING_NAMES[encoding], worst))


# ---------------------------------------------------------------------------
#  7. skin patches
# ---------------------------------------------------------------------------
SKIN_HUES = [12.0, 16.0, 20.0, 24.0, 27.0, 30.0, 34.0, 38.0, 42.0]


def skin_patches(encoding, sat=0.4, val=0.75):
    return [from_display(hsv(h, sat, val), encoding) for h in SKIN_HUES]


def test_skin_operators():
    section("7. skin patches: every control does what it says")
    for encoding in ENCODINGS:
        name = ENCODING_NAMES[encoding]
        patches = skin_patches(encoding)
        meas_in = [sel_measure(px, encoding) for px in patches]

        def run(**kw):
            out = run_dctl(SkinGuardParams(encoding=encoding, **kw), patches)
            return out, [sel_measure(px, encoding) for px in out]

        # consolidate
        _, m = run(consolidate=100)
        spread_in = np.std([ref.hue_delta(x[0], 27.0) for x in meas_in])
        spread_out = np.std([ref.hue_delta(x[0], 27.0) for x in m])
        check(spread_out < 0.3 * spread_in, "%s: Consolidate 100 cuts skin hue spread %.1f -> %.1f deg" %
              (name, spread_in, spread_out))
        check(all(abs(ref.hue_delta(b[0], 27.0)) <= abs(ref.hue_delta(a[0], 27.0)) + 0.05
                  for a, b in zip(meas_in, m)), "%s: Consolidate never pushes a hue away from the line" % name)
        check(all(abs(b[2] - a[2]) < 0.01 for a, b in zip(meas_in, m)),
              "%s: Consolidate keeps skin luma" % name)

        # redness only acts below the line, yellow / green only above
        out, m = run(redness=100)
        # sides by the hue the DCTL measures (in Log direct that is the hue of
        # the log values, not the display hue the patch was built from)
        below = [i for i, a in enumerate(meas_in) if ref.hue_delta(a[0], 27.0) < -1.0]
        above = [i for i, a in enumerate(meas_in) if ref.hue_delta(a[0], 27.0) > 1.0]
        check(all(bits(out[i]) == bits(patches[i]) for i in above) and
              all(ref.hue_delta(m[i][0], meas_in[i][0]) > 1.0 for i in below),
              "%s: Redness moves only red-side skin, towards the line" % name)
        out, m = run(yellow_green=100)
        check(all(bits(out[i]) == bits(patches[i]) for i in below) and
              all(ref.hue_delta(m[i][0], meas_in[i][0]) < -1.0 for i in above),
              "%s: Yellow Green moves only yellow-side skin, towards the line" % name)

        # the hue pull asked for in Rec.709 is the one delivered
        p = SkinGuardParams(encoding=encoding, consolidate=50)
        d = ref._Derived(p)
        worst = 0.0
        for a, px in zip(meas_in, patches):
            dd = ref.hue_delta(a[0], 27.0)
            m_sl = ref.sat_luma_mask(a[1], a[2], d.sat_lo, d.sat_hi, d.sat_feather,
                                     d.luma_lo, d.luma_hi, d.luma_feather)
            want = ref.pull_hue(dd, d.k_red, d.k_yellow, m_sl, d.half_width, d.hue_feather) - dd
            got = ref.hue_delta(sel_measure(run_dctl(p, [px])[0], encoding)[0], a[0])
            worst = max(worst, abs(got - want))
        check(worst < 0.01, "%s: delivered hue pull within %.3f deg of the requested pull" % (name, worst))

        # protect: a look pushed skin yellow and pale; protect brings it back
        graded = [from_display(hsv(h, 0.15, 0.7), encoding) for h in (44.0, 48.0, 52.0)]
        gm = [sel_measure(px, encoding) for px in graded]
        out = run_dctl(SkinGuardParams(encoding=encoding, protect=100), graded)
        om = [sel_measure(px, encoding) for px in out]
        check(all(abs(ref.hue_delta(b[0], 27.0)) < 0.5 * abs(ref.hue_delta(a[0], 27.0)) for a, b in zip(gm, om)),
              "%s: Protect pulls look-shifted skin hue back towards the line" % name)
        check(all(b[1] > a[1] * 1.4 for a, b in zip(gm, om)),
              "%s: Protect restores washed-out skin saturation" % name)
        oversat = [from_display(hsv(25.0, 0.7, 0.8), encoding)]
        o = sel_measure(run_dctl(SkinGuardParams(encoding=encoding, protect=100, natural_sat=35), oversat)[0], encoding)
        check(o[1] < sel_measure(oversat[0], encoding)[1] - 0.1, "%s: Protect calms over-saturated skin" % name)

        # skin saturation keeps luma
        _, up = run(skin_sat=100)
        _, dn = run(skin_sat=-100)
        mid = SKIN_HUES.index(27.0)
        check(up[mid][1] > meas_in[mid][1] * 1.2 and dn[mid][1] < meas_in[mid][1] * 0.8,
              "%s: Skin Saturation raises / lowers skin saturation" % name)
        wv = ref.to_working(patches[mid], encoding)
        o_up = ref.to_working(run_dctl(SkinGuardParams(encoding=encoding, skin_sat=60), [patches[mid]])[0], encoding)
        lsel_in = ref.luma(ref.selection_rgb(wv, encoding))
        lsel_out = ref.luma(ref.selection_rgb(o_up, encoding))
        check(abs(lsel_out - lsel_in) < 1e-5, "%s: Skin Saturation keeps luma (%.1e)" % (name, abs(lsel_out - lsel_in)))

        # exposure: one stop at 100 on a fully selected pixel
        _, ex = run(exposure=100)
        check(ex[mid][2] > meas_in[mid][2] + 0.05, "%s: Skin Exposure brightens skin" % name)
        if encoding in (ENC_LOG, ENC_DWG, ENC_ACESCCT, ENC_CINEON, ENC_LINEAR):
            o = ref.to_working(run_dctl(SkinGuardParams(encoding=encoding, exposure=100), [patches[mid]])[0], encoding)
            if encoding == ENC_LINEAR:
                gain = run_dctl(SkinGuardParams(encoding=encoding, exposure=100), [patches[mid]])[0][1] / patches[mid][1]
                check(abs(gain - 2.0) < 1e-3, "%s: Skin Exposure +100 is exactly +1 stop (x%.4f)" % (name, gain))
            else:
                off = o[1] - wv[1]
                check(abs(off - ref.log_stop(encoding)) < 1e-5,
                      "%s: Skin Exposure +100 is exactly +1 stop (offset %.5f)" % (name, off))

        # density: saturated skin darker than pale skin
        pale = from_display(hsv(27.0, 0.2, 0.75), encoding)
        deep = from_display(hsv(27.0, 0.6, 0.75), encoding)
        o = run_dctl(SkinGuardParams(encoding=encoding, density=100), [pale, deep])
        dl_pale = sel_measure(o[0], encoding)[2] - sel_measure(pale, encoding)[2]
        dl_deep = sel_measure(o[1], encoding)[2] - sel_measure(deep, encoding)[2]
        check(dl_deep < dl_pale < 0.0, "%s: Density darkens saturated skin more (%.3f vs %.3f)" %
              (name, dl_deep, dl_pale))

        # non-skin is left alone
        others = [from_display(hsv(h, 0.6, 0.7), encoding) for h in (120.0, 180.0, 220.0, 280.0)]
        out = run_dctl(SkinGuardParams(encoding=encoding, **EXTREME_SETTINGS[5]), others)
        check(all(bits(a) == bits(b) for a, b in zip(out, others)), "%s: greens, blues, purples untouched" % name)


# ---------------------------------------------------------------------------
#  8. evenness
# ---------------------------------------------------------------------------
def test_evenness():
    section("8. Evenness: colour only, no bleeding")
    rng = random.Random(8)
    w, h = 48, 32
    for encoding in ENCODINGS:
        name = ENCODING_NAMES[encoding]
        frame = []
        for y in range(h):
            for x in range(w):
                if x >= 40:                                   # dark hair strip
                    frame.append(from_display(hsv(25.0, 0.5, 0.12 + 0.02 * rng.random()), encoding))
                elif x < 4:                                   # blue background strip
                    frame.append(from_display(hsv(215.0, 0.5, 0.6), encoding))
                else:                                         # blotchy skin with luma texture
                    blotch = 6.0 * math.sin(x * 0.45) * math.cos(y * 0.5)
                    hue = 27.0 + blotch + rng.uniform(-3, 3)
                    sat = 0.4 + rng.uniform(-0.06, 0.06)
                    val = 0.7 + 0.08 * math.sin(x * 2.1 + y * 1.3)
                    frame.append(from_display(hsv(hue, sat, val), encoding))
        p = SkinGuardParams(encoding=encoding, evenness=100, even_radius=4 * 1920 / w)
        out = run_dctl(p, frame, w, h)
        skin_idx = [y * w + x for y in range(4, h - 4) for x in range(10, 34)]
        win = [ref.to_working(frame[i], encoding) for i in skin_idx]
        wout = [ref.to_working(out[i], encoding) for i in skin_idx]
        hue_in = np.std([sel_measure(frame[i], encoding)[0] for i in skin_idx])
        hue_out = np.std([sel_measure(out[i], encoding)[0] for i in skin_idx])
        check(hue_out < 0.6 * hue_in, "%s: skin hue variation %.2f -> %.2f deg" % (name, hue_in, hue_out))
        dl = max(abs(ref.luma(a) - ref.luma(b)) for a, b in zip(win, wout))
        check(dl < 2e-5, "%s: luma (detail) kept, max change %.1e" % (name, dl))
        tex_in = np.std([ref.luma(a) for a in win])
        tex_out = np.std([ref.luma(a) for a in wout])
        check(abs(tex_out - tex_in) < 1e-5, "%s: texture contrast unchanged" % name)
        bg = [y * w + x for y in range(h) for x in range(0, 4)]
        check(all(bits(out[i]) == bits(frame[i]) for i in bg), "%s: background not touched" % name)
        hair = [y * w + x for y in range(h) for x in range(40, 48)]
        hair_shift = max(abs(a - b) for i in hair for a, b in zip(ref.to_working(out[i], encoding),
                                                                ref.to_working(frame[i], encoding)))
        check(hair_shift < 0.01, "%s: dark hair next to skin barely affected (%.1e)" % (name, hair_shift))

        # a smooth skin gradient stays smooth and ordered
        grad = [from_display(hsv(10.0 + 35.0 * x / (w - 1), 0.45, 0.7), encoding) for y in range(4) for x in range(w)]
        out = run_dctl(SkinGuardParams(encoding=encoding, evenness=100, consolidate=60, even_radius=3 * 1920 / w),
                       grad, w, 4)
        row = unwrap([sel_measure(out[2 * w + x], encoding)[0] for x in range(w)])
        check(min(np.diff(row)) > -1e-3, "%s: Evenness keeps a smooth gradient ordered" % name)

        # reference agrees on an Evenness frame
        r = ref.process_frame(frame, w, h, p)
        a = run_dctl(p, frame, w, h)
        diff = max(max(abs(x - y) for x, y in zip(pa, pb)) for pa, pb in zip(a, r))
        check(diff < 2e-4, "%s: Evenness DCTL == reference (%.1e)" % (name, diff))


# ---------------------------------------------------------------------------
#  9. extremes
# ---------------------------------------------------------------------------
def test_extremes():
    section("9. extreme values: finite and in range")
    rng = random.Random(9)
    wild = awkward_pixels(rng, 200) + [(1e6, 1e6, 0.0), (-1e3, 0.0, 1e3), (1e-30, 1e-30, 0.0), (0.0, 0.0, 1e-20)]
    wild = [f32px(p) for p in wild]
    combos = EXTREME_SETTINGS + [dict(consolidate=100, protect=100, skin_sat=100, density=-100,
                                      exposure=100, evenness=100, hue_centre=c, hue_width=120,
                                      softness=0, sat_low=0) for c in (0.0, 60.0)]
    for encoding in ENCODINGS:
        name = ENCODING_NAMES[encoding]
        ok = True
        for s in combos:
            out = run_dctl(SkinGuardParams(encoding=encoding, **s), wild, 12, len(wild) // 12) \
                if len(wild) % 12 == 0 else run_dctl(SkinGuardParams(encoding=encoding, **s), wild)
            ok = ok and all(finite(px) for px in out)
        check(ok, "%s: no NaN / Inf for any input under extreme settings" % name)

    # display-referred input in [0,1] stays in [0,1]
    grid = [f32px(hsv(h, s, v)) for h in np.arange(0, 70, 2.5) for s in np.linspace(0, 1, 11)
            for v in np.linspace(0, 1, 11)]
    lo, hi = 1.0, 0.0
    for s in combos:
        out = run_dctl(SkinGuardParams(encoding=ENC_DISPLAY, **s), grid, 11, len(grid) // 11)
        lo = min(lo, min(min(px) for px in out))
        hi = max(hi, max(max(px) for px in out))
    check(lo >= -1e-5 and hi <= 1.0 + 1e-5, "Display: [0,1] input stays in [0,1] (got %.6f .. %.6f)" % (lo, hi))


# ---------------------------------------------------------------------------
# 10. preview and amount
# ---------------------------------------------------------------------------
def test_preview_amount():
    section("10. Show Skin Mask and Overall Amount")
    rng = random.Random(10)
    for encoding in ENCODINGS:
        name = ENCODING_NAMES[encoding]
        px = [from_display(skin_like(rng), encoding) for _ in range(200)]
        p = SkinGuardParams(encoding=encoding, show_mask=SM_MASK)
        out = run_dctl(p, px)
        check(all(0.0 <= o[0] <= 1.0 and o[0] == o[1] == o[2] for o in out), "%s: mask is grey in [0,1]" % name)
        exp = [ref.skin_mask(x, p) for x in px]
        check(max(abs(o[0] - e) for o, e in zip(out, exp)) < 1e-4, "%s: mask matches the reference" % name)
        centre = from_display(hsv(27.0, 0.4, 0.75), encoding)
        check(run_dctl(p, [centre])[0][0] > 0.999, "%s: skin on the line is fully selected" % name)
        iso = run_dctl(SkinGuardParams(encoding=encoding, show_mask=SM_ISOLATE), [centre])[0]
        check(max(abs(a - b) for a, b in zip(iso, centre)) < 1e-5, "%s: Isolate keeps skin in colour" % name)

        full = run_dctl(SkinGuardParams(encoding=encoding, consolidate=100, skin_sat=80), px)
        half = run_dctl(SkinGuardParams(encoding=encoding, consolidate=100, skin_sat=80, amount=50), px)
        err = max(abs(h - 0.5 * (a + f)) for a, fp, hp in zip(px, full, half) for a, f, h in zip(a, fp, hp))
        check(err < 1e-5, "%s: Amount 50 is the halfway mix (%.1e)" % (name, err))


def main():
    build = subprocess.run(["sh", os.path.join(HERE, "build.sh")], capture_output=True, text=True)
    if build.returncode != 0:
        print(build.stdout + build.stderr)
        print("BUILD FAILED")
        return 1
    print(build.stdout.strip())

    test_static()
    test_cross_validation()
    test_identity()
    test_neutrals()
    test_hue_sweeps()
    test_sat_luma_sweeps()
    test_skin_operators()
    test_evenness()
    test_extremes()
    test_preview_amount()

    print("\n%d checks, %d failed" % (_checks, len(_failures)))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
