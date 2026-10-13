"""
Tests for MC ACES Contrast: compiles the generated DCTL on the host (C++11 and
C99, -Werror) and checks it against the Python reference.

    python3 tests/test_aces_contrast.py
"""
import os
import re
import subprocess
import sys
import tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mc_aces_contrast as m          # noqa: E402

DCTL = os.path.join(ROOT, "MC_ACES-Contrast-v%s.dctl" % m.VERSION)
TEMPLATE = os.path.join(ROOT, "src", "MC_ACES-Contrast.dctl.in")
BUILD = os.path.join(tempfile.gettempdir(), "mca_build")
EXE = os.path.join(BUILD, "mca_harness")
UI = dict(blend="uiBlend", diffusion="uiDiffusion", density="uiDensity", compensation="uiCompensation",
          hue="uiHue", midtones="uiMidtones", contrast_curve="uiContrastCurve", shadows="uiShadows",
          satfix="uiSatFix", contrast="uiContrast", pivot="uiPivot", saturation="uiSaturation",
          exposure="uiExposure", bypass="uiBypass", space="uiSpace")
STRENGTHS = ("diffusion", "density", "hue", "midtones", "contrast_curve", "shadows", "satfix")

FAILS = []
COUNT = [0]


def check(ok, what):
    COUNT[0] += 1
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILS.append(what)


# ---------------------------------------------------------------------------
#  Build
# ---------------------------------------------------------------------------
def ui_params(src):
    return re.findall(r"^DEFINE_UI_PARAMS\((\w+),\s*([^,]+),\s*(\w+),\s*([^,)]+)", src, re.M)


def build():
    os.makedirs(BUILD, exist_ok=True)
    src = open(DCTL, encoding="utf-8").read()
    f, i = [], []
    for name, _, kind, _ in ui_params(src):
        (f if kind == "DCTLUI_SLIDER_FLOAT" else i).append(name)
    params = os.path.join(BUILD, "mca_params.h")
    with open(params, "w") as fh:
        fh.write("static FloatParam g_f[] = {\n%s\n};\n" % ",\n".join('    { "%s", &%s }' % (n, n) for n in f))
        fh.write("static IntParam g_i[] = {\n%s\n};\n" % ",\n".join('    { "%s", &%s }' % (n, n) for n in i))
    common = ["-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-function",
              "-I", HERE, '-DMCA_LUT_DIR="%s"' % ROOT]
    subprocess.check_call(["g++", "-std=c++11"] + common +
                          ['-DMCA_DCTL="%s"' % DCTL, '-DMCA_PARAMS="%s"' % params,
                           os.path.join(HERE, "mca_harness.cpp"), "-o", EXE])
    # the DCTL on its own as C99 (closer to Resolve's GPU back ends)
    c_src = os.path.join(BUILD, "mca_c_check.c")
    with open(c_src, "w") as fh:
        fh.write('#include "mca_shim.h"\n#include "%s"\n'
                 'int main(void) { float3 o = transform(1, 1, 0, 0, 0.4f, 0.4f, 0.4f); return o.x > 2.0f; }\n' % DCTL)
    subprocess.check_call(["gcc", "-std=c99", "-lm"] + common + [c_src, "-o", os.path.join(BUILD, "mca_c_check"), "-lm"])


def run(px, **kw):
    px = np.asarray(px, dtype=float).reshape(-1, 3)
    args = ["%s=%r" % (UI[k], float(v) if UI[k] not in ("uiBypass", "uiSpace") else int(v)) for k, v in kw.items()]
    inp = "".join("%r %r %r\n" % tuple(float(v) for v in c) for c in px)
    out = subprocess.run([EXE] + args, input=inp, capture_output=True, text=True, check=True).stdout
    return np.array([[float.fromhex(v) for v in line.split()] for line in out.splitlines()])


def ref(px, **kw):
    return m.pixel(np.asarray(px, dtype=float).reshape(-1, 3), **kw)


def rel_err(a, b):
    """|a - b| relative to the size of the value (float32 DCTL vs float64 reference)"""
    return np.abs(a - b) / (1.0 + np.abs(b))


def grey_dwg(x):
    x = np.asarray(x, dtype=float)
    return m.cct_to_dwg(np.stack([x, x, x], -1))


def sample_pixels(n, seed):
    rng = np.random.default_rng(seed)
    lum = rng.uniform(0.1, 0.85, (n, 1))
    cct = lum + rng.normal(0.0, 0.08, (n, 3))
    px = m.cct_to_dwg(cct)
    extra = rng.uniform(0.0, 1.05, (n, 3))
    # keep colours inside AP1: far outside it ACEScct runs to -100 and beyond,
    # where only float32 precision would be compared
    extra = extra[np.all(m.dwg_to_cct(extra) > -0.05, axis=1)][: n // 4]
    return np.vstack([px, extra])


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------
def test_static():
    print("static")
    src = open(DCTL, encoding="utf-8").read()
    banner = "// MarkCaptures MC ACES Contrast\n// © 2026 Mark van der Vis / MarkCaptures\n// www.markcaptures.com\n"
    check(src.startswith(banner), "banner at the top")
    check(src.rstrip("\n").endswith(banner.rstrip("\n")), "banner at the bottom")
    check(re.search(r"^__DEVICE__ float3 transform\(int p_Width, int p_Height, int p_X, int p_Y, "
                    r"float p_R, float p_G, float p_B\)$", src, re.M) is not None, "transform() on one line")
    check("_exp10f" not in src, "no _exp10f")
    check("@@" not in src, "no unfilled placeholders")
    params = ui_params(src)
    names = [p[0] for p in params]
    tips = set(re.findall(r"^DEFINE_UI_TOOLTIP\((\w+),", src, re.M))
    check(set(names) <= tips, "every control has a tooltip")
    kinds = [p[2] for p in params]
    order = {"DCTLUI_SLIDER_FLOAT": 0, "DCTLUI_CHECK_BOX": 1, "DCTLUI_COMBO_BOX": 2}
    check([order[k] for k in kinds] == sorted(order[k] for k in kinds), "sliders, then checkboxes, then combos")
    defaults = {p[0]: float(p[3]) for p in params}
    ok = all(abs(defaults[UI[k]] - float(v)) < 1e-9 for k, v in m.DEFAULTS.items())
    check(ok, "UI defaults match the reference model")
    consts = re.findall(r"__CONSTANT__ float \w+\[(\w+)\]", src)
    sizes = {"MCA_CURVE_N": m.CURVE_N, "MCA_HUE_N": m.HUE_N}
    total = sum(4 * (sizes[c] if c in sizes else int(c)) for c in consts)
    check(total < 60000, "constant tables %d bytes (< 64 KB)" % total)
    luts = re.findall(r"^DEFINE_LUT\(\w+, ([^)]+)\)", src, re.M)
    check(sorted(luts) == sorted(m.LUT_FILES.values()), "DEFINE_LUT names the shipped cubes")
    check(all(os.path.exists(os.path.join(ROOT, f)) for f in luts), "cube files are next to the DCTL")
    for f in luts:
        with open(os.path.join(ROOT, f)) as fh:
            head = [fh.readline() for _ in range(6)]
        check(any(h.startswith("LUT_3D_SIZE 65") for h in head), "%s is a 65 point 3D LUT" % f)
    check(src == open(DCTL, encoding="utf-8").read(), "generated file is current")


def test_cross():
    print("DCTL vs reference")
    px = sample_pixels(1200, 1)
    a, b = run(px), ref(px)
    e = rel_err(a, b)
    check(np.percentile(e, 99.5) < 2e-4 and e.max() < 2e-3,
          "defaults: p99.5 %.2e max %.2e" % (np.percentile(e, 99.5), e.max()))
    rng = np.random.default_rng(7)
    for t in range(6):
        kw = {k: float(rng.choice([0.0, 50.0, 100.0, 150.0, 200.0])) for k in STRENGTHS}
        kw.update(compensation=float(rng.uniform(-1, 1)), contrast=float(rng.uniform(0.7, 1.4)),
                  pivot=float(rng.uniform(0.3, 0.5)), saturation=float(rng.uniform(0.5, 1.5)),
                  exposure=float(rng.uniform(-1, 1)), blend=float(rng.uniform(30, 100)))
        a, b = run(px[:400], **kw), ref(px[:400], **kw)
        e = rel_err(a, b)
        check(np.percentile(e, 99.5) < 3e-4 and e.max() < 3e-3,
              "random settings %d: p99.5 %.2e max %.2e" % (t, np.percentile(e, 99.5), e.max()))
    cct = m.dwg_to_cct(px[:400])
    a, b = run(cct, space=1), ref(cct, space=1)
    e = rel_err(a, b)
    check(np.percentile(e, 99.5) < 2e-4 and e.max() < 2e-3, "ACEScct mode: max %.2e" % e.max())


def test_identity():
    print("identity")
    px = sample_pixels(300, 2)
    check(np.array_equal(run(px, bypass=1), px.astype(np.float32).astype(float)), "Bypass is bit exact")
    check(np.array_equal(run(px, blend=0), px.astype(np.float32).astype(float)), "Blend 0 is bit exact")
    off = {k: 0.0 for k in STRENGTHS}
    e = np.abs(run(px, compensation=0.0, **off) - px)
    check(e.max() < 1e-4, "every node at 0: round trip error %.1e" % e.max())


def test_nodes():
    print("nodes")
    off = {k: 0.0 for k in STRENGTHS}
    # LUT nodes read the lattice exactly: on lattice points the result is the LUT entry
    rng = np.random.default_rng(3)
    for name in ("density", "satfix"):
        L = m.lut(name)
        n = L.shape[0]
        idx = rng.integers(0, n, (300, 3))
        px = idx / (n - 1.0)
        kw = dict(off, compensation=0.0)
        kw[name] = 100.0
        a = run(px, **kw)
        # Diffusion etc. are off, but the ACEScct round trip still runs: compare with the reference
        b = ref(px, **kw)
        lat = L[idx[:, 2], idx[:, 1], idx[:, 0]]
        check(np.abs(a - b).max() < 2e-4, "%s alone matches the reference (max %.1e)" % (name, np.abs(a - b).max()))
        inside = np.all((m.dwg_to_cct(px) > 0.0) & (m.dwg_to_cct(px) < 1.2), axis=1)
        check(np.percentile(np.abs(a - lat)[inside], 99) < 1e-3,
              "%s alone returns the exported LUT on its lattice (p99 %.1e)" % (name, np.percentile(np.abs(a - lat)[inside], 99)))
    # Compensation is an exposure in linear
    g = grey_dwg(np.linspace(0.2, 0.8, 50))
    a = m.di_dec(run(g, **dict(off, compensation=-0.3)))
    check(np.abs(a / m.di_dec(g) - 2 ** -0.3).max() < 2e-4, "Compensation -0.30 stop is exact")
    # Midtones only touches its key band
    x = np.linspace(0.05, 1.0, 400)
    a = m.dwg_to_cct(run(grey_dwg(x), **dict(off, compensation=0.0, midtones=100.0)))[:, 1]
    far = (x < 0.45) | (x > 0.75)
    check(np.abs(a - x)[far].max() < 1e-4, "Midtones leaves greys outside its key alone")
    check(np.abs(a - x)[~far].max() > 0.01, "Midtones changes greys in its key (%.3f)" % np.abs(a - x)[~far].max())
    # Shadows changes blue only
    px = sample_pixels(200, 4)
    a, b = run(px, **dict(off, compensation=0.0, shadows=100.0)), run(px, **dict(off, compensation=0.0))
    cr, cb = m.dwg_to_cct(a), m.dwg_to_cct(b)
    check(np.abs(cr[:, :2] - cb[:, :2]).max() < 1e-4 and np.abs(cr[:, 2] - cb[:, 2]).max() > 0.01,
          "Shadows only moves the blue channel (ACEScct)")
    # Hue Adjustments leaves greys alone
    g = grey_dwg(np.linspace(0.1, 0.9, 60))
    check(np.abs(run(g, **dict(off, compensation=0.0, hue=200.0)) - g).max() < 5e-5, "Hue Adjustments keeps greys neutral")


def test_tone():
    print("tone curve")
    x = np.linspace(0.0, 1.05, 1500)
    g = grey_dwg(x)
    a = m.dwg_to_cct(run(g))
    d = np.diff(a, axis=0) / np.diff(x)[:, None]
    check(d.min() > 0.2, "defaults: grey ramp rises everywhere (min slope %.2f)" % d.min())
    check(np.abs(a[:, 0] - a[:, 1]).max() < 2e-3 and np.abs(a[:, 1] - a[:, 2])[x > 0.6].max() < 3e-3,
          "greys stay near neutral above the Shadows key")
    for k in ("midtones", "diffusion", "contrast_curve", "density"):
        for s in (50.0, 150.0, 200.0):
            a = m.dwg_to_cct(run(g, **{k: s}))
            d = np.diff(a, axis=0) / np.diff(x)[:, None]
            check(d.min() > 0.05, "%s %g: grey ramp rises (min slope %.2f)" % (k, s, d.min()))
    for s in (50.0, 150.0):
        a = m.dwg_to_cct(run(g, shadows=s))
        d = np.diff(a, axis=0) / np.diff(x)[:, None]
        check(d.min() > 0.05, "shadows %g: grey ramp rises (min slope %.2f)" % (s, d.min()))


def main():
    build()
    for t in (test_static, test_identity, test_cross, test_nodes, test_tone):
        t()
    print("\n%d checks, %d failed" % (COUNT[0], len(FAILS)))
    for f in FAILS:
        print("  FAILED:", f)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
