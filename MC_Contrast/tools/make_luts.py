"""
Builds the shipped cubes in MarkCaptures/source/ from Resolve's exports in
data/resolve/.

MarkCaptures MC Contrast
(c) 2026 Mark van der Vis / MarkCaptures - www.markcaptures.com
All rights reserved; see ../LICENSE.txt.

Resolve clips every LUT it exports to 0 .. 1.  The real nodes push some very
dark (and some very bright, saturated) colours past that, and later nodes in
a grade (a print emulation, a black lift) bring that range back into view, so
a clipped LUT shows a flat floor in the blacks.  The clipped entries of each
output channel are rebuilt as the smoothest continuation of the rest: they
minimise the squared second differences along r, g and b over the lattice
(a minimum-curvature fill, which carries the slopes on past the clip), with
every entry Resolve exported unclipped held fixed.  An entry clipped at 0 is
kept in LOW_LIMIT .. 0 and one clipped at 1 in 1 .. HIGH_LIMIT: near the clip
the fill follows the curves, far out in unexported corners of the cube it would
run away, so how far it may go is limited.  Black at the lattice origin stays 0.

    python3 tools/make_luts.py
"""
import os
import numpy as np
import mc_contrast as m

SOURCES = {"density": "density.cube", "hue": "hue.cube", "contrast": "contrast.cube",
           "shadows": "shadows.cube", "satfix": "satfix.cube"}
TITLES = {"density": "Density", "hue": "Hue Adjustments", "contrast": "Contrast",
          "shadows": "Shadows", "satfix": "Sat. Fix"}
EPS = 1e-7
ITERATIONS = 4000
LOW_LIMIT, HIGH_LIMIT = -0.25, 1.25        # DaVinci Intermediate code values


def second_differences(n):
    """Sparse operator: all second differences along the three lattice axes."""
    import scipy.sparse as sp
    idx = np.arange(n ** 3).reshape(n, n, n)
    mats = []
    for ax in range(3):
        a = np.moveaxis(idx, ax, -1)
        i0, i1, i2 = a[..., :-2].ravel(), a[..., 1:-1].ravel(), a[..., 2:].ravel()
        r = np.arange(len(i0))
        mats.append(sp.csr_matrix((np.r_[np.ones(len(r)), -2.0 * np.ones(len(r)), np.ones(len(r))],
                                   (np.r_[r, r, r], np.r_[i0, i1, i2])), shape=(len(r), n ** 3)))
    return sp.vstack(mats).tocsr()


def unclip(L, D=None):
    """L[b][g][r][c] in 0 .. 1 -> the same with clipped entries continued past 0 and 1."""
    import scipy.sparse.linalg as sla
    n = L.shape[0]
    D = second_differences(n) if D is None else D
    out = L.copy()
    for c in range(3):
        u = L[..., c].ravel().copy()
        lo, hi = u <= EPS, u >= 1.0 - EPS
        unknown = lo | hi
        unknown[0] = False                       # black stays black
        if not unknown.any():
            continue
        Du, Dk = D[:, unknown], D[:, ~unknown]
        rows = np.flatnonzero(np.asarray(abs(Du).sum(axis=1)).ravel() > 0)
        x = sla.lsqr(Du[rows], -(Dk[rows] @ u[~unknown]), atol=1e-10, btol=1e-10, iter_lim=ITERATIONS)[0]
        u[unknown] = np.where(lo[unknown], np.clip(x, LOW_LIMIT, 0.0), np.clip(x, 1.0, HIGH_LIMIT))
        out[..., c] = u.reshape(n, n, n)
    return out


def write_cube(path, L, title):
    n = L.shape[0]
    flat = L.reshape(-1, 3)
    with open(path, "w", newline="\n") as fh:
        fh.write('TITLE "MC Contrast - %s (DWG/DI)"\n' % title)
        fh.write("# MarkCaptures MC Contrast - (c) 2026 Mark van der Vis / MarkCaptures - www.markcaptures.com\n")
        fh.write("# Keep this file in MarkCaptures/source/, next to MC_Contrast-v%s.dctl\n" % m.VERSION)
        fh.write("# Resolve export of the node; entries Resolve clipped at 0 and 1 are continued past them\n")
        fh.write("LUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" % n)
        for r, g, b in flat:
            fh.write("%.7g %.7g %.7g\n" % (r, g, b))


def limit(U, L):
    """Apply the limits to an already filled LUT U of the export L (same as unclip's last step)."""
    lo, hi = L <= EPS, L >= 1.0 - EPS
    lo[0, 0, 0] = hi[0, 0, 0] = False
    return np.where(lo, np.clip(U, LOW_LIMIT, 0.0), np.where(hi, np.clip(U, 1.0, HIGH_LIMIT), U))


def main():
    out_dir = os.path.join(m.ROOT, m.LUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    D = None
    for name, src in SOURCES.items():
        L = m.load_cube(os.path.join(m.ROOT, "data", "resolve", src))
        if D is None:
            D = second_differences(L.shape[0])
        U = unclip(L, D)
        changed = np.abs(U - L) > 0
        path = os.path.join(out_dir, m.LUT_FILES[name])
        write_cube(path, U, TITLES[name])
        print("wrote %s: %d of %d entries continued past the clip (min %.3f, max %.3f)"
              % (path, changed.sum(), L.size, U.min(), U.max()))


if __name__ == "__main__":
    main()
