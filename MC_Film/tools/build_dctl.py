#!/usr/bin/env python3
"""Build MC_Film-Core-v<version>.dctl from the template and the stock data.

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Usage:
    python3 tools/build_dctl.py --profiles <spektrafilm>/src/spektrafilm/data/profiles
    python3 tools/build_dctl.py            # reuse data/mcfilm_tables.json

The first form reads the spektrafilm stock profiles (CC BY-SA 4.0) and writes
the reduced tables to data/mcfilm_tables.json; both forms then generate the
DCTL from src/MC_Film-Core.dctl.in.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mcfilm_model as m  # noqa: E402

VERSION = "0.2"
TABLES_JSON = os.path.join(ROOT, "data", "mcfilm_tables.json")
TEMPLATE = os.path.join(ROOT, "src", "MC_Film-Core.dctl.in")
OUTPUT = os.path.join(ROOT, "MC_Film-Core-v%s.dctl" % VERSION)

DATA_NOTICE = """\
//  STOCK DATA - LICENCE NOTICE
//  The tables in this section are derived from the spektrafilm film and print
//  profiles by Andrea Volpato:
//      https://github.com/andreavolpato/spektrafilm
//      Licensed CC BY-SA 4.0 - https://creativecommons.org/licenses/by-sa/4.0/
//  Modified by Mark van der Vis / MarkCaptures (2026): spectra resampled from
//  5 nm to 10 nm, characteristic curves resampled to %d points and made
//  non-decreasing, unmeasured dye / base bands filled from the nearest
//  measured value, spectra pre-multiplied with the printer lamp and the
//  viewing light, exposure matrices and print balance offsets computed.
//  This section (and only this section) is available under CC BY-SA 4.0.
//  The CIE 1931 observer, illuminants and the Mallett & Yuksel 2019 basis
//  used to compute it come from colour-science (BSD-3-Clause).
"""


def c_array(name, values, per_line=8):
    flat = np.asarray(values, dtype=float).ravel()
    assert np.all(np.isfinite(flat)), name
    flat = np.where(np.abs(flat) < 1e-30, 0.0, flat)        # no float32 denormals

    def lit(v):
        s = "%.8g" % v
        if "." not in s and "e" not in s:
            s += ".0"
        return s + "f"

    lines = []
    for i in range(0, len(flat), per_line):
        lines.append("    " + ", ".join(lit(v) for v in flat[i:i + per_line]))
    return "__CONSTANT__ float %s[%d] = {\n%s\n};\n" % (name, len(flat), ",\n".join(lines))


def derived(t):
    """The pre-multiplied tables the DCTL uses (computed by the model)."""
    m.prepare(t)
    return (np.array([p["lampsens"] for p in t["prints"]]),
            np.array([p["viewcmf"] for p in t["prints"]]))


def generate(t):
    lampsens, viewcmf = derived(t)
    negs, prts = t["negs"], t["prints"]
    tables = DATA_NOTICE % m.CURVE_N + "\n"
    tables += "#define MCF_NNEG %d\n#define MCF_NPRT %d\n\n" % (len(negs), len(prts))
    tables += c_array("MCF_NEG_MATRIX", [n["matrix"] for n in negs])
    tables += c_array("MCF_NEG_LOGE_MID", [n["loge_mid"] for n in negs])
    tables += c_array("MCF_NEG_D_MID", [n["d_mid"] for n in negs])
    tables += c_array("MCF_NEG_CURVES", [n["curves"] for n in negs])
    tables += c_array("MCF_NEG_DYES", [n["dyes"] for n in negs])
    tables += c_array("MCF_NEG_BASE", [n["base"] for n in negs])
    tables += c_array("MCF_PRT_LAMPSENS", lampsens)
    tables += c_array("MCF_PRT_CURVES", [p["curves"] for p in prts])
    tables += c_array("MCF_PRT_LOGE", [[p["loge_min"], p["loge_max"]] for p in prts])
    tables += c_array("MCF_PRT_DYES", [p["dyes"] for p in prts])
    tables += c_array("MCF_PRT_BASE", [p["base"] for p in prts])
    tables += c_array("MCF_PRT_VIEWCMF", viewcmf)
    tables += c_array("MCF_PRT_CAT", [p["cat"] for p in prts])
    tables += c_array("MCF_BALANCE", t["balance"])
    tables += c_array("MCF_PIVOT", t["pivot"])
    tables += c_array("MCF_PRT_D_MID", t["print_d_mid"])
    tables += c_array("MCF_PRT_VSLOPE_MID", t["print_vslope_mid"])
    tables += c_array("MCF_PRT_DSLOPE_MID", t["print_dslope_mid"])

    src = open(TEMPLATE, encoding="utf-8").read()
    subs = {
        "VERSION": VERSION,
        "TABLES": tables,
        "INPUT_ENUMS": ", ".join(e for e, _ in m.INPUTS),
        "INPUT_NAMES": ", ".join(n for _, n in m.INPUTS),
        "NEG_ENUMS": ", ".join(e for e, _, _ in m.NEGATIVES),
        "NEG_NAMES": ", ".join(n for _, n, _ in m.NEGATIVES),
        "PRT_ENUMS": ", ".join(e for e, _, _ in m.PRINTS),
        "PRT_NAMES": ", ".join(n for _, n, _ in m.PRINTS),
        "OUT_ENUMS": ", ".join(e for e, _ in m.OUTPUTS),
        "OUT_NAMES": ", ".join(n for _, n in m.OUTPUTS),
        "CURVE_N": str(m.CURVE_N),
        "NEG_LOGE_MIN": repr(m.NEG_LOGE_MIN),
        "NEG_LOGE_MAX": repr(m.NEG_LOGE_MAX),
        "PRINTER_POINT": repr(m.PRINTER_POINT),
        "PUSH_A": repr(m.PUSH_A),
        "PUSH_B": repr(m.PUSH_B),
        "BLEACH_AUTH_K": repr(m.BLEACH_MODES["authentic"][0]),
        "BLEACH_AUTH_E": repr(m.BLEACH_MODES["authentic"][1]),
        "BLEACH_GRUNGE_K": repr(m.BLEACH_MODES["grunge"][0]),
        "BLEACH_GRUNGE_E": repr(m.BLEACH_MODES["grunge"][1]),
        "GAMUT_THRESHOLD": repr(m.GAMUT_THRESHOLD),
        "GAMUT_LIMIT": repr(m.GAMUT_LIMIT),
        "GAMUT_POWER": repr(m.GAMUT_POWER),
    }
    for k, v in subs.items():
        src = src.replace("@@%s@@" % k, v)
    assert "@@" not in src, "unreplaced template field"
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(src)
    return OUTPUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", help="spektrafilm data/profiles directory")
    args = ap.parse_args()
    if args.profiles:
        t = m.build_tables(args.profiles)
        m.save_tables(t, TABLES_JSON)
        print("wrote", TABLES_JSON)
    t = m.load_tables(TABLES_JSON)
    out = generate(t)
    print("wrote", out, "(%d KB)" % (os.path.getsize(out) // 1024))


if __name__ == "__main__":
    main()
