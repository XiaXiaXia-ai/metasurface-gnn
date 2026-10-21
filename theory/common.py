# -*- coding: utf-8 -*-
"""common.py -- shared constants, geometry, data I/O and metrics.

Conventions used by every model in this package
-----------------------------------------------
A model returns a *scalar* aperture amplitude on a direction grid

    S(u, v) = sum_n  w_n * E_n(theta, phi) * exp(j k (x_m u + y_n v)),   u = sin(th)cos(ph)

and the total RCS is

    sigma(theta, phi) = |C * P(theta, phi) * S|^2 ,        C = 2*sqrt(pi)/lambda

where P is the vector projection factor of the aperture field on the
(normalised) spherical basis:

    scalar convention : P_th = cos(theta),          P_ph = 0        (default, matches M0)
    vector convention : P_th = cos(theta)cos(phi),  P_ph = -sin(phi)

Both give the same broadside value.  With w_n = 1 for every cell and
P_th = cos(theta) the model collapses to the PEC plate,

    sqrt(sigma) = 2*sqrt(pi)/lambda * A_tot * cos(theta)
    sigma(0)    = 4*pi*A_tot^2/lambda^2 = 85.9 m^2 = 19.34 dBsm,

which is the mandatory self-check of every model (see models.self_check).

Units: lengths in millimetres inside the model code (P = 14 mm, lambda =
29.979 mm), sigma in m^2.  The constant C carries the mm -> m conversion.
"""
from __future__ import annotations

import numpy as np

# ----------------------------------------------------------------- constants
C0_MM_GHZ = 299.792458          # c in mm*GHz  (lambda[mm] = C0_MM_GHZ / f[GHz])
P_MM = 14.0                     # unit-cell period
N_SIDE = 20                     # 20 x 20 physical cells
BLOCK = 2                       # 2x2 physical cells per macro bit  -> 10x10 bits
N_BITS = N_SIDE // BLOCK        # 10
A_CELL_MM2 = P_MM ** 2          # 196 mm^2
A_TOT_MM2 = (N_SIDE * P_MM) ** 2  # 78400 mm^2 = 0.0784 m^2
F0_GHZ = 10.0
LAM0_MM = C0_MM_GHZ / F0_GHZ    # 29.9792458 mm
Z0 = 376.730313668

# 1-bit states, isolated-cell Floquet simulation at 10 GHz
GAMMA_ABS = (0.867, 0.852)                        # |Gamma| of bit 0 / bit 1
GAMMA_DB = (-1.24, -1.39)                         # 20 log10 |Gamma|
GAMMA_PH_DEG = (-5.3, 174.6)                      # arg Gamma (deg)
GAMMA = tuple(a * np.exp(1j * np.radians(p)) for a, p in zip(GAMMA_ABS, GAMMA_PH_DEG))
GAMMA_DEG = np.degrees(np.angle(GAMMA[1] / GAMMA[0])) % 360.0   # 179.95 deg

# baseline 10x10 code (row index = x, column index = y)
CODE_BASE = ("1101010001", "0001000000", "0011110101", "0000101101", "0001000100",
             "1100110011", "1111100000", "0010000110", "1011111011", "1010111001")
# second random code (dataset case 0001, res_0001.json)
CODE_0001 = ("101110111000000110011000000010101100011000101100011001011100110100100001"
             "0000110110111001011011011100")

DATA_1DEG = r"D:\ff_er265_r2_b2\ff_%s.txt"          # 6 cols, 1 deg grid, 0..180 / 0..359
DATA_2DEG = r"D:\dataset\results\ff\ff_%04d.txt"    # 4 cols, 2 deg grid, 0..90 / 0..358
FREQS = ("9.8", "9.9", "10", "10.1", "10.2")

# 1-bit geometry: disk patch area fraction of a cell
PATCH_R_MM = (4.7, 2.0)
PATCH_COVER = tuple(np.pi * r * r / A_CELL_MM2 for r in PATCH_R_MM)  # 0.354 / 0.064


# -------------------------------------------------------------- small helpers
def lam_mm(f_ghz):
    return C0_MM_GHZ / f_ghz


def plate_dbsm(f_ghz=10.0):
    """RCS of a PEC plate of the same footprint: 4*pi*A^2/lambda^2."""
    a_m2 = A_TOT_MM2 * 1e-6
    lam_m = lam_mm(f_ghz) * 1e-3
    return 10.0 * np.log10(4.0 * np.pi * a_m2 ** 2 / lam_m ** 2)


def const_C(f_ghz=10.0):
    """sigma = |C * sum_n w_n exp(...)|^2 with w_n = 1 -> PEC plate."""
    return 2.0 * np.sqrt(np.pi) / lam_mm(f_ghz) * A_CELL_MM2 * 1e-3


def code_from_string(code10):
    """10x10 bit string (row-major, 100 chars) -> 20x20 physical 0/1 map."""
    bits = np.array([int(c) for c in code10], dtype=int).reshape(N_BITS, N_BITS)
    return np.repeat(np.repeat(bits, BLOCK, axis=0), BLOCK, axis=1), bits


def base_code_map():
    return code_from_string("".join(CODE_BASE))


def code_0001_map():
    return code_from_string(CODE_0001)


def cell_coords(n_side=N_SIDE, p_mm=P_MM):
    """Cell centres; axis 0 = x (row index i -> x_i), axis 1 = y."""
    x = (np.arange(n_side) - (n_side - 1) / 2.0) * p_mm
    X, Y = np.meshgrid(x, x, indexing="ij")
    return x, X, Y


def gamma_map(code_map, gamma=GAMMA):
    """Per-cell complex reflection weight from the 20x20 0/1 map."""
    return np.where(np.asarray(code_map) == 0, gamma[0], gamma[1])


# ------------------------------------------------------------------ angle grid
class Grid:
    """Flattened (theta, phi) grid in degrees plus derived direction cosines."""

    def __init__(self, theta, phi):
        self.th = np.asarray(theta, dtype=float).ravel()
        self.ph = np.asarray(phi, dtype=float).ravel()
        self.t = np.radians(self.th)
        self.p = np.radians(self.ph)
        self.u = np.sin(self.t) * np.cos(self.p)
        self.v = np.sin(self.t) * np.sin(self.p)
        self.uth = np.unique(np.round(self.th, 6))
        self.uph = np.unique(np.round(self.ph, 6))
        self.nth, self.nph = self.uth.size, self.uph.size

    def __len__(self):
        return self.th.size

    def to_grid(self, vals):
        """Flat values -> (n_theta, n_phi) array (theta-major, as CST exports)."""
        return np.asarray(vals).reshape(self.nth, self.nph)

    def cut(self, phi_deg):
        """Mask of the samples on the meridian phi = phi_deg."""
        return np.isclose(self.ph, phi_deg)

    def cut_nearest(self, phi_deg):
        """Mask of the meridian closest to phi_deg (2 deg grids have no phi = 45)."""
        m = np.isclose(self.ph, phi_deg)
        if m.any():
            return m
        used = self.uph[np.argmin(np.abs(self.uph - phi_deg))]
        return np.isclose(self.ph, used)

    def idx(self, theta, phi):
        return int(np.argmin(np.abs(self.th - theta) + np.abs(self.ph - phi)))


def grid_1deg(front_only=True):
    th = np.arange(0, 91, 1, dtype=float) if front_only else np.arange(0, 181, 1.0)
    ph = np.arange(0, 360, 1, dtype=float)
    T, Pp = np.meshgrid(th, ph, indexing="ij")
    return Grid(T.ravel(), Pp.ravel())


def grid_2deg():
    th = np.arange(0, 91, 2, dtype=float)
    ph = np.arange(0, 360, 2, dtype=float)
    T, Pp = np.meshgrid(th, ph, indexing="ij")
    return Grid(T.ravel(), Pp.ravel())


# -------------------------------------------------------------------- data I/O
def load_ff6(path, front_only=True):
    """CST export with phase: theta phi |Eth|dB angEth |Eph|dB angEph (dBsm / deg)."""
    d = np.loadtxt(path)
    if front_only:
        d = d[d[:, 0] <= 90.0]
    g = Grid(d[:, 0], d[:, 1])
    eth = 10 ** (d[:, 2] / 20) * np.exp(1j * np.radians(d[:, 3]))
    eph = 10 ** (d[:, 4] / 20) * np.exp(1j * np.radians(d[:, 5]))
    return g, eth, eph


def load_ff4(path):
    """CST export, amplitude only: theta phi |Eth|dB |Eph|dB (dBsm)."""
    d = np.loadtxt(path)
    g = Grid(d[:, 0], d[:, 1])
    eth = 10 ** (d[:, 2] / 20) * np.ones(len(d))
    eph = 10 ** (d[:, 3] / 20) * np.ones(len(d))
    return g, eth, eph


def total_db(eth, eph):
    """Total RCS in dBsm from the two polarisation channels."""
    return 10 * np.log10(np.abs(eth) ** 2 + np.abs(eph) ** 2 + 1e-30)


# --------------------------------------------------------------------- metrics
def metrics(grid, meas_db, model_db, ref_theta=0.0):
    """Five scalar comparators, identical definitions for every model/case.

    specular_dbsm  : total sigma at theta = ref_theta (model value)
    mean_far_dbsm  : 10 log10 < sigma > over theta in [10, 90], all phi, linear mean
    corr_phiX      : Pearson r of the dB patterns on the phi = X meridian,
                     6 <= theta <= 60 deg, samples with measurement > -30 dB
    rmse_6_60deg   : RMS of (model - measurement) in dB over theta in [6, 60],
                     all phi, samples with measurement > -30 dB
    """
    i0 = int(np.argmin(np.abs(grid.th - ref_theta)))
    spec = float(model_db[i0])

    band = (grid.th >= 10.0) & (grid.th <= 90.0)
    mean_far = float(10 * np.log10(np.mean(10 ** (model_db[band] / 10.0))))

    corr = {}
    for pc in (0, 45, 90):
        # 2 deg exports have no phi = 45 meridian; use the closest one there
        m = grid.cut_nearest(pc) & (grid.th >= 6) & (grid.th <= 60) & (meas_db > -30)
        corr[pc] = float(np.corrcoef(meas_db[m], model_db[m])[0, 1]) if m.sum() > 3 else np.nan

    m = (grid.th >= 6) & (grid.th <= 60) & (meas_db > -30)
    rmse = float(np.sqrt(np.mean((model_db[m] - meas_db[m]) ** 2)))

    return dict(specular_dbsm=spec, mean_far_dbsm=mean_far,
                corr_phi0=corr[0], corr_phi45=corr[45], corr_phi90=corr[90],
                rmse_6_60deg=rmse)


def band_mean_db(grid, pattern_db, th_lo=30.0, th_hi=60.0, phi_deg=None):
    m = (grid.th >= th_lo) & (grid.th <= th_hi)
    if phi_deg is not None:
        m &= grid.cut(phi_deg)
    return float(10 * np.log10(np.mean(10 ** (pattern_db[m] / 10.0))))


# ------------------------------------------------------- separable AF evaluator
def aperture_sum(w, u, v, k, x):
    """S_i = sum_{m,n} w_{mn} exp(j k (x_m u_i + y_n v_i)); O(2 M N) exponentials.

    w is (N, N) with axis 0 = x.  Two-stage sum:
        inner_m(v) = sum_n w_mn exp(j k y_n v)
        S_i        = sum_m exp(j k x_m u_i) inner_m(v_i)
    """
    w = np.asarray(w, dtype=complex)
    if w.ndim == 1:
        w = w.reshape(N_SIDE, N_SIDE)
    ex = np.exp(1j * k * np.outer(v, x))          # (M, N) over y
    inner = w @ ex.T                              # (N, M)
    ex2 = np.exp(1j * k * np.outer(u, x))         # (M, N) over x
    return np.einsum("mn,nm->m", ex2, inner)
