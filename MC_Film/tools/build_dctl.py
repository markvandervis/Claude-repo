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
import mcfilm_effects as fx  # noqa: E402

VERSION = "0.5"
TABLES_JSON = os.path.join(ROOT, "data", "mcfilm_tables.json")
TEMPLATE = os.path.join(ROOT, "src", "MC_Film-Core.dctl.in")
OUTPUT = os.path.join(ROOT, "MC_Film-Core-v%s.dctl" % VERSION)
EFFECTS_VERSION = "0.2"
GRAIN_TEMPLATE = os.path.join(ROOT, "src", "MC_Film-Grain.dctl.in")
GRAIN_OUTPUT = os.path.join(ROOT, "MC_Film-Grain-v%s.dctl" % EFFECTS_VERSION)
HALO_TEMPLATE = os.path.join(ROOT, "src", "MC_Film-Halation.dctl.in")
HALO_VERSION = "0.5"
HALO_OUTPUT = os.path.join(ROOT, "MC_Film-Halation-v%s.dctl" % HALO_VERSION)

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
    tables += c_array("MCF_PRT_CAT", [p["cats"] for p in prts])
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
        "WP_ENUMS": ", ".join(e for e, _, _ in m.WHITES),
        "WP_NAMES": ", ".join(n for _, n, _ in m.WHITES),
        "TINT_DUV": repr(m.TINT_DUV_PER_UNIT),
        "TEMP_REF_K": repr(m.TEMP_REF_K),
        "MIRED_MIN": repr(m.MIRED_MIN),
        **{k: repr(getattr(m, k)) for k in ("XOVER_LOGE_PER_UNIT", "XOVER_ZONE_WIDTH", "XOVER_HOLD_MAX",
                                            "TWIST_MAX_DEG", "ROLLOFF_KNEE", "VIBRANCE_SCALE",
                                            "RICHNESS_LOGE", "HL_DESAT_START", "HL_DESAT_WIDTH")},
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


def fill(template, output, subs):
    src = open(template, encoding="utf-8").read()
    for k, v in subs.items():
        src = src.replace("@@%s@@" % k, v)
    assert "@@" not in src, "unreplaced template field in " + template
    with open(output, "w", encoding="utf-8") as f:
        f.write(src)
    return output


def generate_effects():
    gauge = {"GAUGE_DEFAULT": str([g[0] for g in fx.GAUGES].index("GAUGE_S35")),
             "GAUGE_ENUMS": ", ".join(g[0] for g in fx.GAUGES),
             "GAUGE_NAMES": ", ".join(g[1] for g in fx.GAUGES)}
    widths = [g[2] * 1000.0 for g in fx.GAUGES]
    grain_tables = c_array("MCG_GAUGE_WIDTH_UM", widths)
    grain_tables += c_array("MCG_GRANULARITY", [fx.GRANULARITY_X1000[k] / 1000.0 for _, _, k in m.NEGATIVES])
    out = [fill(GRAIN_TEMPLATE, GRAIN_OUTPUT, dict(gauge, **{
        "VERSION": EFFECTS_VERSION,
        "NEG_ENUMS": ", ".join(e for e, _, _ in m.NEGATIVES),
        "NEG_NAMES": ", ".join(n for _, n, _ in m.NEGATIVES),
        "GRAIN_CELL_UM": repr(fx.GRAIN_CELL_UM),
        "GRAIN_FIELD_NORM": "%.9g" % fx.GRAIN_FIELD_NORM,
        "GRAIN_TABLES": grain_tables}))]
    radii, cs, sn = fx.halo_taps()
    halo_tables = c_array("MCH_GAUGE_WIDTH_UM", widths)
    halo_tables += c_array("MCH_TAP_RADIUS", radii) + c_array("MCH_TAP_COS", cs) + c_array("MCH_TAP_SIN", sn)
    out.append(fill(HALO_TEMPLATE, HALO_OUTPUT, dict(gauge, **{
        "VERSION": HALO_VERSION, "HALO_UM": repr(fx.HALO_UM), "HALO_TAPS": str(fx.HALO_TAPS),
        "MATCH_SIZE": repr(fx.MATCH_SIZE), "MATCH_GROWTH": repr(fx.MATCH_GROWTH),
        "MATCH_STRENGTH": repr(fx.MATCH_STRENGTH), "MATCH_COLOUR": repr(fx.MATCH_COLOUR),
        "REF_WIDTH_UM": repr([g[2] for g in fx.GAUGES if g[0] == "GAUGE_S35"][0] * 1000.0),
        "SMALL_WIDTH_UM": repr([g[2] for g in fx.GAUGES if g[0] == "GAUGE_8"][0] * 1000.0),
        "HALO_TABLES": halo_tables})))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", help="spektrafilm data/profiles directory")
    args = ap.parse_args()
    if args.profiles:
        t = m.build_tables(args.profiles)
        m.save_tables(t, TABLES_JSON)
        print("wrote", TABLES_JSON)
    t = m.load_tables(TABLES_JSON)
    for out in [generate(t)] + generate_effects():
        print("wrote", out, "(%d KB)" % (os.path.getsize(out) // 1024))


if __name__ == "__main__":
    main()
