# -*- coding: utf-8 -*-
"""models.py -- seven independent theoretical routes to the far field of the
20 x 20 1-bit coding metasurface.

Every model returns a Field (theta, phi grid + complex E_theta, E_phi) whose
total RCS is sigma = |E_theta|^2 + |E_phi|^2.  All of them are written so that
a *uniform* aperture (w_n = 1) reproduces the PEC plate

    sigma(0) = 4 pi A^2 / lambda^2 = 19.342 dBsm  (10 GHz, A = 0.28 x 0.28 m)

which is checked by self_check() at the bottom of this file.

Model map
---------
M0  af_ideal            array factor, Gamma-weighted cells, cos(theta) oblique
M1  af_element          M0 x fitted element pattern cos^q(theta)
M1b af_element_airy     M0 x analytic element pattern of the 2r disk (no fit)
M2  po_two_region       physical optics, disk patch (Gamma_bit) + gap (Gamma_gap)
                        integrated exactly per cell (Airy + sinc), H2 enters here
M3  rs_farfield         Rayleigh-Sommerfeld, LPR eq. (4), z -> infinity limit
    rs_nearfield_cut    same kernel at finite z (20 lambda / 30 lambda)
M4  as_farfield         angular spectrum / plane-wave expansion, LPR eq. (5)
    as_propagate        FFT transfer function with evanescent cut-off
M6  coupled_dipole      first-order mutual coupling (I - c W) a = Gamma, H1
M5  slab_reflection / lc_element   unit-cell equivalent circuit (no pattern)
"""
from __future__ import annotations

import numpy as np
from scipy import special

import common as C


class Field:
    """Far-field sampling of one model on one (theta, phi) grid."""

    def __init__(self, name, grid, eth, eph, params=None):
        self.name = name
        self.grid = grid
        self.eth = np.asarray(eth, dtype=complex)
        self.eph = np.asarray(eph, dtype=complex)
        self.params = dict(params or {})

    @property
    def db(self):
        return C.total_db(self.eth, self.eph)

    @property
    def sigma(self):
        return np.abs(self.eth) ** 2 + np.abs(self.eph) ** 2


def _finish(name, grid, S, f_ghz, projection="scalar", params=None):
    """Apply the aperture-to-far-field constant and the polarisation projection."""
    amp = C.const_C(f_ghz) * S
    if projection == "scalar":
        eth = amp * np.cos(grid.t)
        eph = np.zeros_like(amp)
    elif projection == "vector":
        eth = amp * np.cos(grid.t) * np.cos(grid.p)
        eph = -amp * np.sin(grid.p)
    else:
        raise ValueError(projection)
    return Field(name, grid, eth, eph, params)


# --------------------------------------------------------------- M0: array factor
def af_ideal(grid, f_ghz, code_map, gamma=C.GAMMA, projection="scalar", weights=None):
    """M0 -- ideal 1-bit aperture.

        sqrt(sigma) = 2 sqrt(pi)/lambda * cos(theta) * A_cell
                      * sum_n Gamma_bit(n) exp[j k (x_m sin th cos ph + y_n sin th sin ph)]

    Assumptions: each cell is a point source carrying the *isolated-cell* Floquet
    reflection coefficient; no mutual coupling, no finite-cell aperture factor, no
    edge.  A_cell = 196 mm^2 is the area represented by one point.  With every
    Gamma = 1 the sum equals 400 and sigma = 4 pi A^2 / lambda^2 (PEC plate).
    """
    k = 2 * np.pi / C.lam_mm(f_ghz)
    x, X, Y = C.cell_coords()
    w = C.gamma_map(code_map, gamma) if weights is None else np.asarray(weights)
    S = C.aperture_sum(w.reshape(C.N_SIDE, C.N_SIDE), grid.u, grid.v, k, x)
    return _finish("M0_AF", grid, S, f_ghz, projection,
                   dict(gamma=list(gamma), projection=projection))


# ------------------------------------------------- M1: array factor + element pattern
def af_element(grid, f_ghz, code_map, q=0.0, scale=1.0, gamma=C.GAMMA,
               projection="scalar"):
    """M1 -- M0 multiplied by a cos^q(theta) embedded-element pattern.

        sqrt(sigma) = scale * cos^q(theta) * sqrt(sigma_M0)

    q and scale are fitted on the measured pattern (theta 6..60 deg).  Note the
    structural limitation: cos^q(0) = 1 for any q, so no element pattern that is
    normalised at boresight can raise the *specular* level; M1 can only reshape
    the diffuse part.  That is why it is a control model for the 13.8 dB gap.
    """
    base = af_ideal(grid, f_ghz, code_map, gamma=gamma, projection=projection)
    amp = scale * np.cos(grid.t) ** q
    return Field("M1_AF+element", grid, base.eth * amp, base.eph * amp,
                 dict(q=q, scale=scale, projection=projection))


def af_element_airy(grid, f_ghz, code_map, r_mm=4.7, scale=1.0, gamma=C.GAMMA,
                    projection="scalar"):
    """M1b -- element pattern of the real circular patch, no free parameter.

    A uniform in-phase disk of radius r radiates the Airy pattern

        f_e(theta) = 2 J1(k r sin theta) / (k r sin theta)

    (f_e(0) = 1).  For r = 4.7 mm (0.157 lambda) the first null is at
    sin theta = 1.22 lambda / (2r) = 3.9, i.e. outside the visible region, so the
    element is essentially isotropic: this model says the cos(theta) of M0 is an
    obliquity factor, not the element pattern.
    """
    base = af_ideal(grid, f_ghz, code_map, gamma=gamma, projection=projection)
    q = 2 * np.pi / C.lam_mm(f_ghz) * r_mm * np.sin(grid.t)
    fe = np.where(q < 1e-9, 1.0, 2 * special.j1(q) / np.where(q < 1e-9, 1.0, q))
    amp = scale * fe
    return Field("M1b_AF+airy", grid, base.eth * amp, base.eph * amp,
                 dict(r_mm=r_mm, scale=scale))


# ------------------------------------------------------------- M2: physical optics
def po_two_region(grid, f_ghz, code_map, gamma_gap=None, gamma=C.GAMMA,
                  projection="scalar", r_mm=C.PATCH_R_MM, coverage_scale=1.0):
    """M2 -- physical optics over the *real* sub-cell geometry (H2 enters here).

    Surface current / equivalent aperture field:

        J(r') = 2 n x (n x E_refl)/Z0 ,   E_refl = Gamma_bit E_inc on the disk,
                                          Gamma_gap E_inc on the bare substrate

    Far field (Fraunhofer limit of the radiation integral):

        E = -jk Z0/(4 pi r) e^{-jkr} Int_S J e^{j k r'.rhat} dS

    which, with the 2 n x (n x .) factor and J = 2 Gamma E_inc/Z0, is identical to
    the scalar aperture integral with obliquity cos(theta):

        sqrt(sigma) = 2 sqrt(pi)/lambda cos(theta) sum_cells [
              Gamma_bit A_p(r_bit) * airy(r_bit,theta)
            + Gamma_gap (P^2 sinc(k P u/2) sinc(k P v/2) - A_p airy(r_bit,theta)) ]
            * exp[j k (x_m u + y_n v)]

    with airy(r) = 2 J1(k r sin th)/(k r sin th) the exact disk integral and the
    square-minus-disk the exact gap integral, both referred to the cell centre.

    Parameters
    ----------
    gamma_gap : complex, default 1.0 * exp(j 142 deg) (grounded-slab TL value)
    coverage_scale : multiplies the patch area (1.0 = the fabricated geometry;
        0.0 = no metal at all, i.e. the pure unmodulated background)
    """
    if gamma_gap is None:
        gamma_gap = slab_gamma(f_ghz)
    k = 2 * np.pi / C.lam_mm(f_ghz)
    x, X, Y = C.cell_coords()
    rcell = np.where(np.asarray(code_map) == 0, r_mm[0], r_mm[1]).astype(float)
    ap = coverage_scale * np.pi * rcell ** 2
    st = np.sin(grid.t)

    def airy(rv):
        q = k * rv * st
        safe = np.where(q < 1e-9, 1.0, q)
        return np.where(q < 1e-9, 1.0, 2 * special.j1(safe) / safe)

    sincx = np.sinc(k * C.P_MM * grid.u / (2 * np.pi))
    sincy = np.sinc(k * C.P_MM * grid.v / (2 * np.pi))
    cell_sq = C.P_MM ** 2 * sincx * sincy          # square-cell integral

    S_all = C.aperture_sum(np.ones((C.N_SIDE, C.N_SIDE)), grid.u, grid.v, k, x)
    S = np.zeros_like(S_all, dtype=complex)
    for bit in (0, 1):
        m = (np.asarray(code_map) == bit)
        if not m.any():
            continue
        a_b = airy(np.unique(rcell[m])[0])          # radius is uniform inside a bit
        S += C.aperture_sum(m.astype(float), grid.u, grid.v, k, x) * (
            (gamma[bit] - gamma_gap) * ap[m].mean() * a_b)
    S += gamma_gap * cell_sq * S_all
    # S carries an area (mm^2); _finish expects the 'sum of unit weights' form
    return _finish("M2_PO", grid, S / C.A_CELL_MM2, f_ghz, projection,
                   dict(gamma_gap=complex(gamma_gap), coverage_scale=coverage_scale))


# ------------------------------------------- M3: Rayleigh-Sommerfeld (LPR eq. 4)
def rs_farfield(grid, f_ghz, code_map, gamma=C.GAMMA, projection="scalar"):
    """M3 -- Rayleigh-Sommerfeld diffraction, z -> infinity.

    LPR 2025 eq. (4):

        E(x,y,z) = Int Int (z/l^2) (1/(2 pi l) + 1/(j lambda)) e^{-j 2 pi l/lambda}
                   E(x',y',0) dx' dy' ,      l = sqrt((x-x')^2+(y-y')^2+z^2)

    Aperture: the 20 x 20 array is treated as a *piecewise-constant* field on
    14 mm x 14 mm square cells (not point samples), because eq. (4) integrates a
    continuous field.  The cell integral is exact:

        Int_cell e^{j k r'.rhat} dS' = P^2 sinc(k P u/2) sinc(k P v/2)
                                       * exp(j k R_n.rhat)

    and in the far zone z/l -> cos(theta), 1/l -> 1/R, so

        sqrt(sigma) = 2 sqrt(pi)/lambda cos(theta) * [M0 sum] * P^2 sinc sinc / A_cell

    i.e. M3 = M0 x (finite-cell aperture factor).  The 1/(2 pi l) term of eq. (4)
    is O(1/l^3) against 1/l^2 and is shown in rs_nearfield_cut to change the
    20 lambda field by < 1e-3 dB.
    """
    k = 2 * np.pi / C.lam_mm(f_ghz)
    x, X, Y = C.cell_coords()
    w = C.gamma_map(code_map, gamma)
    S = C.aperture_sum(w, grid.u, grid.v, k, x)
    cell = np.sinc(k * C.P_MM * grid.u / (2 * np.pi)) * np.sinc(
        k * C.P_MM * grid.v / (2 * np.pi))
    return _finish("M3_RS", grid, S * cell, f_ghz, projection,
                   dict(discretisation="piecewise-constant cell, exact cell FT"))


def _aperture_pixels(f_ghz, code_map, gamma=C.GAMMA, dx_mm=1.0, half_mm=140.0):
    """Sampled piecewise-constant aperture field of the array (mm, mm)."""
    n = int(round(2 * half_mm / dx_mm)) + 1
    xs = np.linspace(-half_mm, half_mm, n)
    XX, YY = np.meshgrid(xs, xs, indexing="ij")
    i = np.clip(np.round((XX + half_mm - C.P_MM / 2) / C.P_MM).astype(int), 0, C.N_SIDE - 1)
    j = np.clip(np.round((YY + half_mm - C.P_MM / 2) / C.P_MM).astype(int), 0, C.N_SIDE - 1)
    w = C.gamma_map(code_map, gamma)
    return xs, XX, YY, w[i, j]


def rs_nearfield_cut(f_ghz, code_map, z_mm, theta_deg, gamma=C.GAMMA, dx_mm=1.0,
                     two_term=True, chunk=40):
    """Rayleigh-Sommerfeld (LPR eq. 4) propagated to a finite distance z.

    Field points lie on the phi = 0 half plane, (x, y, z) = (z tan th, 0, z), and
    the aperture is the sampled piecewise-constant field of the array.  The direct
    O(N_ap x N_obs) sum is used, so this is the literal spatial-domain version of
    eq. (4) -- no FFT, no paraxial approximation.

    Returns (E, l_mean) with E the complex scalar field (same normalisation as
    af_ideal: a uniform unit aperture gives sqrt(sigma_plate) at z -> infinity).
    """
    lam = C.lam_mm(f_ghz)
    k = 2 * np.pi / lam
    xs, XX, YY, Ea = _aperture_pixels(f_ghz, code_map, gamma, dx_mm=dx_mm)
    dA = dx_mm ** 2
    th = np.radians(np.asarray(theta_deg, dtype=float))
    xo = z_mm * np.tan(th)
    out = np.zeros(th.size, dtype=complex)
    for s in range(0, th.size, chunk):
        sl = slice(s, min(s + chunk, th.size))
        dx = xo[sl, None] - XX.ravel()[None, :]
        dy = -YY.ravel()[None, :]
        l = np.sqrt(dx * dx + dy * dy + z_mm ** 2)
        kern = z_mm / l ** 2 * np.exp(-1j * k * l)
        if two_term:
            kern = kern * (1.0 / (2 * np.pi * l) + 1.0 / (1j * lam))
        else:
            kern = kern * (1.0 / (1j * lam))
        out[sl] = (kern * Ea.ravel()[None, :]).sum(axis=1) * dA
    return out, k


# ------------------------------------------------- M4: angular spectrum (LPR eq. 5)
def _as_grid(f_ghz, code_map, gamma=C.GAMMA, dx_mm=2.0, n_fft=4096):
    """Aperture on an n_fft x n_fft grid, centred, with zero padding."""
    lam = C.lam_mm(f_ghz)
    half = n_fft * dx_mm / 2.0
    n_ap = int(round(2 * 140.0 / dx_mm))
    ii = np.arange(n_ap) - (n_ap - 1) / 2.0
    # cell centres sit at (k - (N-1)/2) * P ; left edge of the array at -140 mm
    edge = C.P_MM * (C.N_SIDE - 1) / 2.0
    i = np.clip(np.round((ii * dx_mm + edge) / C.P_MM).astype(int), 0, C.N_SIDE - 1)
    w = C.gamma_map(code_map, gamma)
    ap = w[np.ix_(i, i)]
    fld = np.zeros((n_fft, n_fft), dtype=complex)
    c0 = n_fft // 2 - n_ap // 2
    fld[c0:c0 + n_ap, c0:c0 + n_ap] = ap
    fx = np.fft.fftshift(np.fft.fftfreq(n_fft, d=dx_mm))     # 1/mm
    return fld, fx * lam, lam, half


_SPEC_CACHE = {}


def _as_spectrum(f_ghz, code_map, gamma=C.GAMMA, dx_mm=2.0, n_fft=4096):
    """Visible-region spectrum F(u,v) = Int E(x,y) exp(+j k (x u + y v)) dx dy.

    Cached: the paper-form and cos-obliquity variants share one FFT.
    """
    key = (round(f_ghz, 6), dx_mm, n_fft, int(np.asarray(code_map).sum()),
           hash(np.asarray(code_map).tobytes()), hash(np.asarray(gamma).tobytes()))
    if key in _SPEC_CACHE:
        return _SPEC_CACHE[key]
    fld, u_ax, lam, half = _as_grid(f_ghz, code_map, gamma, dx_mm, n_fft)
    # +j sign convention:  F(u,v) = sum E exp(+j k (x u + y v)) = N^2 * ifft2(E)
    spec = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(fld))) * n_fft ** 2 * dx_mm ** 2
    sel = np.abs(u_ax) <= 1.0
    out = (u_ax[sel], spec[np.ix_(sel, sel)], lam)
    _SPEC_CACHE[key] = out
    return out


def as_propagate(field0, dx_mm, lam_mm, z_mm, evanescent=True):
    """Angular-spectrum propagation, H = exp(j kz z), kz = sqrt(k0^2-kx^2-ky^2).

    Evanescent components (|k_xy| > k0) get kz = j sqrt(kxy^2-k0^2) and are
    attenuated by exp(-|kz| z); with evanescent=False they are simply dropped
    (that is the usual 'propagating only' truncation, and the two agree to
    1e-6 dB for z >= 1 lambda because exp(-2 pi z/lambda_sqrt..) is tiny).
    """
    n = field0.shape[0]
    k0 = 2 * np.pi / lam_mm
    fx = np.fft.fftshift(np.fft.fftfreq(n, d=dx_mm)) * 2 * np.pi    # kx, 1/mm
    KX, KY = np.meshgrid(fx, fx, indexing="ij")
    kxy2 = KX ** 2 + KY ** 2
    prop = kxy2 <= k0 ** 2
    KZ = np.zeros_like(KX, dtype=complex)
    KZ[prop] = np.sqrt(k0 ** 2 - kxy2[prop])
    if evanescent:
        KZ[~prop] = 1j * np.sqrt(kxy2[~prop] - k0 ** 2)
    H = np.exp(1j * KZ * z_mm)
    spec = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(field0)))
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(spec * H)))


def as_farfield(grid, f_ghz, code_map, gamma=C.GAMMA, obliquity="cos",
                dx_mm=2.0, n_fft=4096):
    """M4 -- plane-wave (angular-spectrum) expansion to the far field, LPR eq. (5).

        E(r,th,ph) = j k e^{-jkr}/(2 pi r) [ th (fx cos ph + fy sin ph)
                       + ph cos(th) (-fx sin ph + fy cos ph) ]        (paper form)

    with (fx, fy) the vector spectrum of the aperture field at kx = k sin th cos ph,
    ky = k sin th sin ph.  For an x-polarised aperture fy = 0.

    The paper's form has no obliquity on the theta component; the classical
    Rayleigh-Sommerfeld result for the same aperture carries a cos(th) factor.
    obliquity = 'cos' multiplies the theta component by cos(th) so that M4 reduces
    to M3 (< 0.1 dB, see compare.py); obliquity = 'paper' reproduces eq. (5)
    verbatim.  Both give 19.34 dBsm at boresight.
    """
    uu, F, lam = _as_spectrum(f_ghz, code_map, gamma, dx_mm, n_fft)

    from scipy.interpolate import RegularGridInterpolator
    ri = RegularGridInterpolator((uu, uu), F.real, bounds_error=False, fill_value=0.0)
    rq = RegularGridInterpolator((uu, uu), F.imag, bounds_error=False, fill_value=0.0)
    pts = np.column_stack([grid.u, grid.v])
    Fr = ri(pts) + 1j * rq(pts)

    k = 2 * np.pi / lam
    # sqrt(sigma) = 2 sqrt(pi) * |j k/(2 pi) * F| = (k/sqrt(pi)) |F|, mm -> m
    amp = 1j * k / np.sqrt(np.pi) * Fr * 1e-3    # r e^{jkr} E  (r set to 1)
    cph, sph = np.cos(grid.p), np.sin(grid.p)
    ct = np.cos(grid.t)
    ob = ct if obliquity == "cos" else np.ones_like(ct)
    eth = amp * ob * cph
    eph = amp * ct * (-sph)
    return Field("M4_AS", grid, eth, eph,
                 dict(obliquity=obliquity, dx_mm=dx_mm, n_fft=n_fft))


def as_nearfield_map(f_ghz, code_map, z_mm, gamma=C.GAMMA, dx_mm=2.0, n_fft=2048):
    """2-D near-field map at distance z (mm) from the angular-spectrum propagator."""
    fld, u_ax, lam, half = _as_grid(f_ghz, code_map, gamma, dx_mm, n_fft)
    out = as_propagate(fld, dx_mm, lam, z_mm)
    n = n_fft
    x = (np.arange(n) - n // 2) * dx_mm
    return x, out


# --------------------------------------------- M6: coupling / phase-compression (H1)
def phase_compress(grid, f_ghz, code_map, alpha=1.0, gamma_abs=None, gamma=C.GAMMA,
                   projection="scalar"):
    """M6 -- effective phase compression of the 1-bit states (H1, one parameter).

        Gamma_n = |Gamma| exp(j alpha phi_bit),    phi_bit = (-5.3, 174.6) deg

    alpha = 1 is the isolated-cell Floquet pair; alpha < 1 compresses the 180 deg
    coding phase (mutual coupling / local-periodicity error).  Because both states
    are rotated toward 0, the *common mode* (Gamma0+Gamma1)/2 no longer vanishes:

        |a| = |Gamma| cos(alpha * 180/2 deg)

    and a uniform in-phase component of that size appears on every cell, i.e. a
    diffraction-limited specular lobe of the full aperture.  |a| = 0.374 requires
    alpha * 180 = 136 deg (for |Gamma| = 1), which is the number quoted in the
    report.  Only the *phase* is rescaled, so sum |Gamma_n|^2 and hence the diffuse
    level are unchanged -- this is what separates H1 from H2.
    """
    if gamma_abs is None:
        gamma_abs = np.abs(gamma[0])
    g = tuple(gamma_abs * np.exp(1j * np.radians(alpha * p)) for p in C.GAMMA_PH_DEG)
    fld = af_ideal(grid, f_ghz, code_map, gamma=g, projection=projection)
    fld.name = "M6_phase_compress"
    fld.params.update(alpha=alpha, gamma_abs=gamma_abs)
    return fld


def coupling_matrix(f_ghz, radius=3, gamma=C.GAMMA):
    """Normalised scalar Green matrix W_mn = (P/r) exp(-j k r), r <= radius*P."""
    k = 2 * np.pi / C.lam_mm(f_ghz)
    x, X, Y = C.cell_coords()
    n = C.N_SIDE
    W = np.zeros((n * n, n * n), dtype=complex)
    xs = X.ravel()
    ys = Y.ravel()
    for a in range(n * n):
        dx = xs[a] - xs
        dy = ys[a] - ys
        r = np.hypot(dx, dy)
        m = (r > 0) & (r <= radius * C.P_MM + 1e-9)
        W[a, m] = (C.P_MM / r[m]) * np.exp(-1j * k * r[m])
    return W


def coupled_dipole(grid, f_ghz, code_map, cpl=0.0, radius=3, gamma=C.GAMMA,
                   projection="scalar", W=None):
    """M6b -- first-order mutual coupling (DDA):  (I - c W) a = Gamma.

    Discrete-dipole / local-field picture: the effective weight of cell n is the
    isolated-cell coefficient plus the field scattered by its neighbours,

        a_n = Gamma_n + c sum_m W_nm a_m ,      W_nm = (P/r_nm) e^{-j k r_nm}

    solved exactly (400 x 400).  c is a single complex coupling constant fitted to
    the measured specular level.  Positive real c makes the array's local field
    lag, which compresses the 180 deg coding phase; c = 0 recovers M0.
    """
    if W is None:
        W = coupling_matrix(f_ghz, radius, gamma)
    g = C.gamma_map(code_map, gamma).ravel()
    A = np.eye(g.size, dtype=complex) - cpl * W
    a = np.linalg.solve(A, g)
    S = C.aperture_sum(a, grid.u, grid.v, 2 * np.pi / C.lam_mm(f_ghz), C.cell_coords()[0])
    return _finish("M6b_DDA", grid, S, f_ghz, projection, dict(cpl=complex(cpl), radius=radius))


def effective_phase_gap(a, code_map):
    """Mean phase of the two bit populations after coupling (deg) and |a|."""
    a = np.asarray(a).ravel()
    cm = np.asarray(code_map).ravel()
    m0, m1 = cm == 0, cm == 1
    p0 = np.mean(a[m0])
    p1 = np.mean(a[m1])
    return (np.degrees(np.angle(p1 / p0)) % 360.0, abs(p0), abs(p1))


# --------------------------------------- M5: unit-cell equivalent circuit (no pattern)
def slab_gamma(f_ghz, er=2.65, tand=0.0013, h_mm=1.5):
    """Reflection coefficient of the bare grounded dielectric slab (TL model).

    Z_in = j Z_d tan(k_d h),  Z_d = Z0/sqrt(eps_r(1-j tan d)),  Gamma = (Z_in-Z0)/(Z_in+Z0).

    Lossless limit |Gamma| = 1 exactly; with tan d = 0.0013 the model gives
    -0.0007 dB.  This is the 'unmodulated background' phase used by H2/M2.
    """
    w = 2 * np.pi * f_ghz * 1e9
    eps = er * (1 - 1j * tand)
    kd = w / 299792458.0 * np.sqrt(eps)
    zd = C.Z0 / np.sqrt(eps)
    zin = 1j * zd * np.tan(kd * h_mm * 1e-3)
    return (zin - C.Z0) / (zin + C.Z0)


def lc_element(f_ghz, r_mm, er=2.65, h_mm=1.5, fringing=1.0):
    """Quasi-static LC model of one cell: disk capacitance over the slab inductance.

        C(r) = eps0 eps_r pi r^2 / h * fringing ,   L = 1/(w_res^2 C),
        w_res(r) = 1.841 c / (r sqrt(eps_r))       (TM11 of a circular patch)

    shunted across the grounded-slab line; Gamma from the total admittance.  The
    model is deliberately parameter-poor: it has no free per-state fit, so the
    comparison with the two Floquet points measures how much of the cell physics
    the equivalent circuit actually captures.
    """
    eps0 = 8.8541878128e-12
    w = 2 * np.pi * f_ghz * 1e9
    eps = er * (1 - 1j * 0.0013)
    c = eps0 * er * np.pi * (r_mm * 1e-3) ** 2 / (h_mm * 1e-3) * fringing
    f_res = 1.841 * 299792458.0 / (2 * np.pi * r_mm * 1e-3 * np.sqrt(er))
    l = 1.0 / ((2 * np.pi * f_res) ** 2 * c)
    y_lc = 1j * w * c + 1.0 / (1j * w * l)
    kd = w / 299792458.0 * np.sqrt(eps)
    zd = C.Z0 / np.sqrt(eps)
    y_slab = 1.0 / (1j * zd * np.tan(kd * h_mm * 1e-3))
    y = y_lc + y_slab
    y0 = 1.0 / C.Z0
    return (y0 - y) / (y0 + y)


# ------------------------------------------------------------------- self-check
def self_check(verbose=True):
    """Uniform-aperture check: every model must give 19.342 dBsm at boresight."""
    g = C.grid_1deg()
    f = 10.0
    ones = np.zeros((C.N_SIDE, C.N_SIDE), dtype=int)
    unit = (1.0 + 0j, 1.0 + 0j)
    rows = []
    rows.append(("M0  af_ideal", af_ideal(g, f, ones, gamma=unit).db[0]))
    rows.append(("M1  af_element(q=0)", af_element(g, f, ones, q=0.0, gamma=unit).db[0]))
    rows.append(("M1b af_element_airy", af_element_airy(g, f, ones, scale=1.0, gamma=unit).db[0]))
    rows.append(("M2  po_two_region", po_two_region(g, f, ones, gamma_gap=1.0 + 0j, gamma=unit).db[0]))
    rows.append(("M3  rs_farfield", rs_farfield(g, f, ones, gamma=unit).db[0]))
    rows.append(("M4  as_farfield", as_farfield(g, f, ones, gamma=unit, n_fft=2048).db[0]))
    rows.append(("M6  coupled_dipole(c=0)", coupled_dipole(g, f, ones, cpl=0.0, gamma=unit).db[0]))
    ref = C.plate_dbsm(f)
    if verbose:
        print("self-check: uniform aperture (all Gamma = 1), 10 GHz, plate = %.3f dBsm" % ref)
        for n, v in rows:
            print("   %-24s %8.3f dBsm   err %+7.4f dB" % (n, v, v - ref))
    return rows, ref


if __name__ == "__main__":
    self_check()
    # M3 <-> M4 far-field cross-check with matched obliquity (<= 0.1 dB required)
    g = C.grid_1deg()
    cm, _ = C.base_code_map()
    a = rs_farfield(g, 10.0, cm)
    b = as_farfield(g, 10.0, cm, obliquity="cos", n_fft=4096)
    m = (g.th <= 60) & (a.db > -20)
    print("M3 vs M4 (matched obliquity) max|d| = %.3f dB over %d samples"
          % (np.max(np.abs(a.db[m] - b.db[m])), m.sum()))
    c = as_farfield(g, 10.0, cm, obliquity="paper", n_fft=4096)
    print("paper eq.(5) vs cos-obliquity: rms %.2f dB (theta 6..60)"
          % np.sqrt(np.mean((c.db[(g.th >= 6) & (g.th <= 60)] - b.db[(g.th >= 6) & (g.th <= 60)]) ** 2)))
