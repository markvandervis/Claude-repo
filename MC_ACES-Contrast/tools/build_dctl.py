"""
Generates MC_ACES-Contrast-v<version>.dctl from src/MC_ACES-Contrast.dctl.in
and the tables in mc_aces_contrast.py.

MarkCaptures MC ACES Contrast
(c) 2026 Mark van der Vis / MarkCaptures - www.markcaptures.com
All rights reserved; see ../LICENSE.txt.

    python3 tools/build_dctl.py
"""
import os
import re
import numpy as np
import mc_aces_contrast as m

TEMPLATE = os.path.join(m.ROOT, "src", "MC_ACES-Contrast.dctl.in")
OUTPUT = os.path.join(m.ROOT, "MC_ACES-Contrast-v%s.dctl" % m.VERSION)


def flt(v):
    return "%.9gf" % float(v)


def table(a, per_line=8):
    vals = [flt(v) for v in np.asarray(a).ravel()]
    rows = [", ".join(vals[i:i + per_line]) for i in range(0, len(vals), per_line)]
    return "\n    " + ",\n    ".join(rows) + "\n"


def generate():
    subs = {"VERSION": m.VERSION, "LUT_N": str(m.lut("density").shape[0]),
            "CURVE_N": str(m.CURVE_N), "HUE_N": str(m.HUE_N),
            "AP1_TO_DWG": ", ".join(flt(v) for v in m.AP1_TO_DWG.ravel()),
            "DWG_TO_AP1": ", ".join(flt(v) for v in m.DWG_TO_AP1.ravel()),
            "DIFFUSION_TABLE": table(m.curve_table(m.KN_DIFFUSION)),
            "CONTRAST_TABLE": table(m.curve_table(m.KN_CONTRAST)),
            "SHADOWS_TABLE": table(m.curve_table(m.KN_SHADOWS)),
            "HUE_HUE_TABLE": table(m.hue_table(m.BZ_HUE_HUE)),
            "HUE_SAT_TABLE": table(m.hue_table(m.BZ_HUE_SAT)),
            "COMPENSATION": "%.2f" % m.COMPENSATION,
            "AP1_YR": "%.10g" % m.AP1_Y[0], "AP1_YG": "%.10g" % m.AP1_Y[1], "AP1_YB": "%.10g" % m.AP1_Y[2],
            "LUMA_R": "%.10g" % m.LUMA[0], "LUMA_G": "%.10g" % m.LUMA[1], "LUMA_B": "%.10g" % m.LUMA[2]}
    for name, kn in (("DIFFUSION", m.KN_DIFFUSION), ("CONTRAST", m.KN_CONTRAST), ("SHADOWS", m.KN_SHADOWS)):
        subs[name + "_M0"] = "%.9g" % kn[2][0]
        subs[name + "_M1"] = "%.9g" % kn[2][-1]
    for k in ("MT_CONTRAST", "MT_PIVOT", "MT_SAT", "MT_LOW", "MT_HIGH", "MT_LOW_SOFT", "MT_HIGH_SOFT",
              "MT_SOFT_K", "MT_SOFT_MARGIN", "SH_LOW", "SH_HIGH", "SH_LOW_SOFT", "SH_HIGH_SOFT", "SH_GAIN"):
        subs[k] = "%.9g" % getattr(m, k)
    src = open(TEMPLATE, encoding="utf-8").read()

    def rep(mo):
        key = mo.group(1)
        if key not in subs:
            raise KeyError("template placeholder @@%s@@ has no value" % key)
        return subs[key]

    out = re.sub(r"@@([A-Z0-9_]+)@@", rep, src)
    # a float literal needs a decimal point or exponent before the f suffix
    out = re.sub(r"(?<![\w.])(\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)f\b",
                 lambda mo: mo.group(0) if re.search(r"[.eE]", mo.group(1)) else mo.group(1) + ".0f", out)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    return OUTPUT


if __name__ == "__main__":
    path = generate()
    print("wrote", path, "(%d KB)" % (os.path.getsize(path) // 1024))
