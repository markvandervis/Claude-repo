"""MC Film - grain and halation: shared tables and reference implementations.

MarkCaptures MC Film - (c) 2026 Mark van der Vis / MarkCaptures.
All rights reserved; see ../LICENSE.txt.

Mirrors src/MC_Film-Grain.dctl.in and src/MC_Film-Halation.dctl.in.  The
integer hash runs in numpy uint32, which wraps exactly like the DCTL's
unsigned int, so the grain pattern is reproduced bit for bit up to float
rounding.
"""

import math

import numpy as np

# --- gauges: frame width of the camera aperture, in millimetres -------------
GAUGES = [
    ("GAUGE_8",   "8mm",          4.80),
    ("GAUGE_S8",  "Super 8",      5.79),
    ("GAUGE_16",  "16mm",         10.26),
    ("GAUGE_S16", "Super 16",     12.52),
    ("GAUGE_S35", "Super 35",     24.89),
    ("GAUGE_65",  "65mm",         52.48),
]

# --- approximate RMS granularity (x 1000, 48 um aperture, density 1.0) -------
# In the spirit of the manufacturers' published figures; the Grain Amount
# slider is the final control.  Order follows mcfilm_model.NEGATIVES.
GRANULARITY_X1000 = {
    "kodak_vision3_50d": 5.0, "kodak_vision3_250d": 6.0, "kodak_vision3_200t": 6.0,
    "kodak_vision3_500t": 8.0, "kodak_portra_160": 4.0, "kodak_portra_400": 4.5,
    "kodak_portra_800": 6.5, "kodak_ektar_100": 4.0, "kodak_gold_200": 7.0,
    "kodak_ultramax_400": 8.0, "fujifilm_pro_400h": 5.0, "fujifilm_c200": 8.0,
    "fujifilm_xtra_400": 9.0, "kodak_verita_200d": 6.0,
}

GRAIN_CELL_UM = 12.0
APERTURE_UM = 48.0
DENSITY_FLOOR = 0.05
GRAIN_FIELD_NORM = 1.0 / math.sqrt(2.0 * (math.pi / 5.0) * (7.0 / 12.0))
LAYER_SIZE = (1.0, 0.9, 1.15)
CINEON_BLACK = 95.0 / 1023.0
CINEON_DPC = 2.046

HALO_UM = 100.0           # radius of the (bloom) glow disc on the film
HALO_EDGE = 0.6           # soft edge of the disc: falls from 0.7 to 1.3 radii
HALO_RED_SPREAD = 1.35    # halation (red, through the base) spreads further than bloom
MATCH_SIZE = 1.0          # Matched mode: Size 1 = HALO_UM on Super 35
MATCH_GROWTH = 0.07       # on-screen size growth (S35 width / gauge width)^0.07
MATCH_STRENGTH = 0.6      # glow strength ~ (S35 width / gauge width)^0.6, from reference screenshots
MATCH_COLOUR = 0.15       # colour 0.15 redder at 8mm
HALO_TAPS = 256
MIDGRAY = 0.184
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


# ---------------------------------------------------------------------------
#  halation kernel table
# ---------------------------------------------------------------------------
def halo_profile(r):
    """The glow kernel: a disc of radius 1 with a soft, linear edge."""
    return min(max((1.0 - r) / HALO_EDGE + 0.5, 0.0), 1.0)


def halo_taps(n=HALO_TAPS):
    """Radial quantiles of the soft-disc kernel (radial pdf r k(r)) on a
    golden-angle spiral."""
    rmax = 1.0 + 0.5 * HALO_EDGE
    grid = np.linspace(0.0, rmax, 20001)
    pdf = grid * np.array([halo_profile(r) for r in grid])
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(grid))])
    cdf /= cdf[-1]
    radii, cos_, sin_ = [], [], []
    for i in range(n):
        radii.append(float(np.interp((i + 0.5) / n, cdf, grid)))
        a = i * GOLDEN_ANGLE
        cos_.append(math.cos(a))
        sin_.append(math.sin(a))
    return np.array(radii), np.array(cos_), np.array(sin_)


# ---------------------------------------------------------------------------
#  hashing (uint32, wraps like the DCTL)
# ---------------------------------------------------------------------------
M32 = 0xFFFFFFFF


def hash32(x):
    x = int(x) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def unit(h):
    return float(h >> 8) * (1.0 / 16777216.0)


# ---------------------------------------------------------------------------
#  grain (scalar mirror of the DCTL)
# ---------------------------------------------------------------------------
def grain_field(x, y, stream):
    cx, cy = math.floor(x), math.floor(y)
    total = 0.0
    for j in (-1, 0, 1):
        for i in (-1, 0, 1):
            h = hash32((((cx + i) & M32) * 0x8da6b343 & M32) ^ (((cy + j) & M32) * 0xd8163841 & M32) ^ stream)
            for _ in range(2):
                h = hash32((h + 0x9e3779b9) & M32)
                gx = (cx + i) + unit(h)
                h = hash32(h)
                gy = (cy + j) + unit(h)
                h = hash32(h)
                r = 0.5 + 0.5 * unit(h)
                s = 1.0 if (h & 1) else -1.0
                t2 = ((x - gx) ** 2 + (y - gy) ** 2) / (r * r)
                if t2 < 1.0:
                    b = 1.0 - t2
                    total += s * b * b
    return total * GRAIN_FIELD_NORM


def layer_grain(px, py, cell_px, layer_size, seed, layer, colour):
    c = cell_px * layer_size
    own = grain_field(px / c, py / c, hash32((seed * 4 + layer) & M32))
    shared = grain_field(px / cell_px, py / cell_px, hash32((seed * 4 + 3) & M32))
    a, b = colour, 1.0 - colour
    return (a * own + b * shared) / math.sqrt(a * a + b * b)


def grain_sigma(density, sigma_cell, shadow):
    dd = max(density, 0.0) + DENSITY_FLOOR
    return sigma_cell * (dd / (1.0 + DENSITY_FLOOR)) ** (0.5 * shadow)


def apply_grain(d, px, py, foot_um, granular, amount, size, colour, shadow, seed):
    cell_um = GRAIN_CELL_UM * size
    cell_px = cell_um / foot_um
    sigma_cell = amount * granular * APERTURE_UM / cell_um
    if cell_px < 1.0:
        sigma_cell *= cell_px
        cell_px = 1.0
    g = [layer_grain(px, py, cell_px, LAYER_SIZE[k], seed, k, colour) for k in range(3)]
    return [d[k] + grain_sigma(d[k], sigma_cell, shadow) * g[k] for k in range(3)]


def grain_pixel(cineon, x, y, width, neg_key, gauge_i, amount=1.0, size=1.0, colour=0.8,
                shadow=1.0, seed=0):
    if amount <= 0.0:
        return tuple(cineon)
    d = [(c - CINEON_BLACK) * CINEON_DPC for c in cineon]
    foot = GAUGES[gauge_i][2] * 1000.0 / width
    out = apply_grain(d, x + 0.5, y + 0.5, foot, GRANULARITY_X1000[neg_key] / 1000.0,
                      amount, size, colour, shadow, int(math.floor(max(seed, 0.0))))
    return tuple(CINEON_BLACK + v / CINEON_DPC for v in out)


# ---------------------------------------------------------------------------
#  halation (mirror of the DCTL)
# ---------------------------------------------------------------------------
def di_decode(y):
    return 2.0 ** (min(y, 5.0) / 0.07329248 - 7.0) - 0.0075 if y > 0.02740668 else y / 10.44426855


def di_encode(x):
    return (math.log2(x + 0.0075) + 7.0) * 0.07329248 if x > 0.00262409 else x * 10.44426855


def threshold(v, thr):
    if thr <= 0.0:
        return max(v, 0.0)
    x = v - thr
    if x <= 0.0:
        return 0.0
    if x >= thr:
        return x - 0.5 * thr
    return x * x / (2.0 * thr)


def halation_frame(frame, width, height, amount=0.10, size=1.0, colour=0.6, threshold_stops=1.0,
                   gauge_i=4, quality=1, bloom=0.35, matched=True):
    """frame: row-major list of DWG / DI pixels.  Returns the same encoding."""
    radii, cs, sn = halo_taps()
    thr = MIDGRAY * 2.0 ** threshold_stops if threshold_stops > 0.0 else 0.0
    gauge_um = GAUGES[gauge_i][2] * 1000.0
    ref_um = [g for g in GAUGES if g[0] == "GAUGE_S35"][0][2] * 1000.0
    small_um = [g for g in GAUGES if g[0] == "GAUGE_8"][0][2] * 1000.0
    if matched:
        g = math.log2(ref_um / gauge_um) / math.log2(ref_um / small_um)
        scale = HALO_UM * MATCH_SIZE * size / (ref_um / width) * (ref_um / gauge_um) ** MATCH_GROWTH
        strength = (ref_um / gauge_um) ** MATCH_STRENGTH
        amount = amount * strength
        bloom = bloom * strength
        colour = max(colour - MATCH_COLOUR * g, 0.0)
    else:
        scale = HALO_UM * size / (gauge_um / width)
    stride = {3: 1, 2: 2, 1: 4, 0: 8}[quality]     # Ultra 256, Best 128, Good 64, Draft 32
    n_taps = HALO_TAPS // stride
    spread = 6.28318531 / (3.0 * math.sqrt(n_taps))
    lin = [[threshold(di_decode(p[c]), thr) for c in range(3)] for p in frame]
    out = []
    for y in range(height):
        for x in range(width):
            c = frame[y * width + x]
            if amount <= 0.0 and bloom <= 0.0:
                out.append(tuple(c))
                continue
            h = hash32((((x & M32) * 0x8da6b343) & M32) ^ (((y & M32) * 0xd8163841) & M32))
            rot = (h >> 8) * (6.28318531 / 16777216.0)
            cr, sr = math.cos(rot), math.sin(rot)
            tot = [0.0, 0.0, 0.0]
            hal = 0.0
            n = 0
            for i in range((h & 7) % stride, HALO_TAPS, stride):
                r = radii[i] * scale
                ox = cs[i] * cr - sn[i] * sr
                oy = sn[i] * cr + cs[i] * sr
                d = spread * r
                for k in (-1, 0, 1):
                    if bloom > 0.0:
                        xx = min(max(x + int(math.floor(ox * r - oy * d * k + 0.5)), 0), width - 1)
                        yy = min(max(y + int(math.floor(oy * r + ox * d * k + 0.5)), 0), height - 1)
                        t = lin[yy * width + xx]
                        tot[0] += t[0]
                        tot[1] += t[1]
                        tot[2] += t[2]
                    if amount > 0.0:
                        rw, dw = r * HALO_RED_SPREAD, d * HALO_RED_SPREAD
                        xx = min(max(x + int(math.floor(ox * rw - oy * dw * k + 0.5)), 0), width - 1)
                        yy = min(max(y + int(math.floor(oy * rw + ox * dw * k + 0.5)), 0), height - 1)
                        hal += lin[yy * width + xx][0]
                    n += 1
            l = [di_decode(v) for v in c]
            own = [threshold(v, thr) for v in l]
            dh = max(hal / n - own[0], 0.0)
            dr, dg, db = [max(tot[k] / n - own[k], 0.0) for k in range(3)]
            new = [l[0] + amount * dh + bloom * dr, l[1] + amount * colour * dh + bloom * dg, l[2] + bloom * db]
            out.append(tuple(c[k] if new[k] == l[k] else di_encode(new[k]) for k in range(3)))
    return out
