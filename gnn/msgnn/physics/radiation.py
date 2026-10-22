# -*- coding: utf-8 -*-
"""Differentiable vector far-field operator (torch) + pointwise numpy reference.

Aperture model (identical to theory/common.py and theory/models.py):

    S(u, v) = sum_n q_n exp[ j k (x_n u + y_n v + z_n w) ],   (u,v,w) = unit dir
    E_theta = C * p_theta(theta,phi) * S
    E_phi   = C * p_phi  (theta,phi) * S
    sigma   = |E_theta|^2 + |E_phi|^2           [m^2, i.e. dBsm]
    C       = 2 sqrt(pi) / lambda * A_cell * 1e-3      (mm -> m)

with A_cell = P^2 the area represented by one node.  A uniform aperture q_n = 1
therefore reproduces the PEC plate 4 pi A^2 / lambda^2 = 19.342 dBsm at 10 GHz,
which is the mandatory self-check of every model.

Polarisation projections
------------------------
    scalar : p_theta = cos(theta),         p_phi = 0
    vector : p_theta = cos(theta)cos(phi), p_phi = -sin(phi)

'vector' is the classical result for an x-polarised aperture field and is the
default: theory/REPORT.md sec. 4.5 shows that the measured E/H asymmetry
(-1.84 dB) is predicted as -1.61 dB by the vector form and as 0.00 dB by the
scalar one.  At theta = 0 both give sigma = |C S|^2, independent of phi.

Geometry is general: nodes carry 3-D positions (curved arrays work unchanged)
and the observation directions are 3-D unit vectors.  The polarisation projection
is the only genuinely planar ingredient and is documented as such.
"""
from typing import Optional, Tuple

import numpy as np
import torch

C0_MM_GHZ = 299.792458
Z0_OHM = 376.730313668


# ------------------------------------------------------------------ constants
def lam_mm(freq_ghz: float) -> float:
    return C0_MM_GHZ / float(freq_ghz)


def const_c(freq_ghz: float = 10.0, period_mm: float = 14.0) -> float:
    """Far-field constant for a lattice of cells of area P^2 (units: mm -> m)."""
    return 2.0 * np.sqrt(np.pi) / lam_mm(freq_ghz) * (period_mm ** 2) * 1e-3


def plate_dbsm(freq_ghz: float = 10.0, n_side: int = 20, period_mm: float = 14.0) -> float:
    """4 pi A^2 / lambda^2 for the full aperture (the 19.342 dBsm reference)."""
    a_m2 = (n_side * period_mm * 1e-3) ** 2
    lam_m = lam_mm(freq_ghz) * 1e-3
    return float(10.0 * np.log10(4.0 * np.pi * a_m2 ** 2 / lam_m ** 2))


# ------------------------------------------------------------------ geometry
def lattice_positions(n_side: int = 20, period_mm: float = 14.0) -> np.ndarray:
    """(n_side^2, 3) cell-centre positions in mm, row-major with axis 0 = x."""
    x = (np.arange(n_side) - (n_side - 1) / 2.0) * period_mm
    X, Y = np.meshgrid(x, x, indexing="ij")
    return np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], axis=1)


def directions(theta_deg, phi_deg) -> np.ndarray:
    """(M, 3) unit vectors; accepts flat or grid-shaped theta/phi of equal size."""
    t = np.radians(np.asarray(theta_deg, dtype=float)).ravel()
    p = np.radians(np.asarray(phi_deg, dtype=float)).ravel()
    t, p = np.broadcast_arrays(t, p)
    return np.stack([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)], axis=1)


def projection_factors(theta_deg, phi_deg, mode: str = "vector") -> Tuple[np.ndarray, np.ndarray]:
    """(p_theta, p_phi) for the aperture polarisation convention."""
    t = np.radians(np.asarray(theta_deg, dtype=float)).ravel()
    p = np.radians(np.asarray(phi_deg, dtype=float)).ravel()
    if mode == "scalar":
        return np.cos(t), np.zeros_like(t)
    if mode == "vector":
        return np.cos(t) * np.cos(p), -np.sin(p)
    raise ValueError("projection must be 'scalar' or 'vector', got %r" % (mode,))


def solid_angle_weights(theta_deg, floor: float = 0.05) -> np.ndarray:
    """w ~ sin(theta) (+floor), normalised to mean 1 (solid-angle sampling)."""
    t = np.radians(np.asarray(theta_deg, dtype=float)).ravel()
    w = np.sin(t) + float(floor)
    return w / w.mean()


# --------------------------------------------------------------- numpy (ref)
def aperture_sum_numpy(q, theta_deg, phi_deg, freq_ghz: float = 10.0,
                       period_mm: float = 14.0, pos_mm: Optional[np.ndarray] = None,
                       n_side: Optional[int] = None) -> np.ndarray:
    """Complex aperture sum S = sum_n q_n exp(j k r_n . s), shape q.shape[:-1]+(M,)."""
    q = np.asarray(q, dtype=complex)
    flat = q.reshape(-1, q.shape[-1])
    if pos_mm is None:
        n = q.shape[-1]
        ns = n_side if n_side else int(round(np.sqrt(n)))
        if ns * ns != n:
            raise ValueError("cannot infer the lattice from %d nodes" % n)
        pos_mm = lattice_positions(ns, period_mm)
    pos = np.asarray(pos_mm, dtype=float)
    dirs = directions(theta_deg, phi_deg)
    k = 2.0 * np.pi / lam_mm(freq_ghz)
    s = flat @ np.exp(1j * (k * (pos @ dirs.T)))
    return s.reshape(q.shape[:-1] + (s.shape[-1],))


def farfield_numpy(q, theta_deg, phi_deg, freq_ghz: float = 10.0,
                   period_mm: float = 14.0, pos_mm: Optional[np.ndarray] = None,
                   projection: str = "vector", scale: float = 1.0,
                   n_side: Optional[int] = None,
                   area_mm2: Optional[np.ndarray] = None):
    """Reference implementation of the operator, pointwise identical to
    theory/models.py:af_ideal(...) followed by _finish(projection=...).

    q may be (N,), (B, N) or any shape whose last axis is the node axis.
    Returns (eth, eph) with shape q.shape[:-1] + (M,).

    area_mm2 (B2 hook): optional per-node effective area in mm^2.  The
    equivalent source strength is q_n * A_n, so the global P^2 factor moves out
    of the constant.  Passing A_n = P^2 reproduces the uniform path up to
    float32 rounding (the numpy reference is exact);
    a curved array is expected to pass its own A_n together with a local frame.
    """
    q = np.asarray(q, dtype=complex)
    if area_mm2 is None:
        c = const_c(freq_ghz, period_mm) * scale
    else:
        q = q * np.asarray(area_mm2, dtype=float)
        c = 2.0 * np.sqrt(np.pi) / lam_mm(freq_ghz) * 1e-3 * scale
    s = aperture_sum_numpy(q, theta_deg, phi_deg, freq_ghz, period_mm, pos_mm, n_side)
    pth, pph = projection_factors(theta_deg, phi_deg, projection)
    amp = c * s
    shape = q.shape[:-1] + (amp.shape[-1],)
    return (amp * pth).reshape(shape), (amp * pph).reshape(shape)


def sigma_from_fields(eth, eph) -> np.ndarray:
    return np.abs(eth) ** 2 + np.abs(eph) ** 2


def to_db(x, floor_db: float = -300.0) -> np.ndarray:
    return np.maximum(10.0 * np.log10(np.maximum(np.asarray(x, dtype=float), 1e-300)),
                      floor_db)


# ------------------------------------------------------------- torch operator
class FarFieldOperator:
    """Torch operator: (q_re, q_im) -> (E_theta, E_phi) complex, batched.

    The phase kernel exp(j k r_n . s_m) is (M, N) and is independent of q, so it
    is precomputed once per (geometry, angle grid).  Complex numbers are carried
    as explicit real/imaginary tensors so that autograd never has to deal with
    complex-conjugation conventions.

    Units: q is dimensionless (q = 1 for every node gives the PEC plate), the
    output field is sqrt(m^2) i.e. sigma = |E|^2 is in m^2 and dBsm = 10 log10.
    """

    def __init__(self, theta_deg, phi_deg, pos_mm: Optional[np.ndarray] = None,
                 freq_ghz: float = 10.0, period_mm: float = 14.0,
                 projection: str = "vector", dtype=torch.float64,
                 chunk_m: int = 0, precompute: bool = True, scale: float = 1.0,
                 n_side: Optional[int] = 20,
                 area_mm2: Optional[np.ndarray] = None):
        self.theta_deg = np.asarray(theta_deg, dtype=float).ravel()
        self.phi_deg = np.asarray(phi_deg, dtype=float).ravel()
        if self.theta_deg.size != self.phi_deg.size:
            raise ValueError("theta and phi must have the same length")
        self.m = self.theta_deg.size
        self.freq_ghz = float(freq_ghz)
        self.period_mm = float(period_mm)
        self.projection = projection
        self.dtype = dtype
        self.scale = float(scale)

        self.dirs_np = directions(self.theta_deg, self.phi_deg)
        if pos_mm is None:
            if n_side is None:
                raise ValueError("either pos_mm or n_side is required")
            pos_mm = lattice_positions(int(n_side), self.period_mm)
        self.pos_np = np.asarray(pos_mm, dtype=float)
        self.n = self.pos_np.shape[0]
        self.k = 2.0 * np.pi / lam_mm(self.freq_ghz)
        self.c = const_c(self.freq_ghz, self.period_mm) * self.scale
        # B2 hook: with a per-node area the source strength is q_n * A_n, so the
        # global P^2 leaves the constant.  area_mm2=None keeps the old numerics.
        self.area_np = None
        self.area = None
        if area_mm2 is not None:
            a = np.asarray(area_mm2, dtype=float).ravel()
            if a.size == 1:                       # a scalar broadcasts like numpy
                a = np.full(self.n, float(a[0]))
            if a.size != self.n:
                raise ValueError("area_mm2 must be a scalar or have one entry per node")
            self.area_np = a
            self.area = torch.as_tensor(a, dtype=dtype)
            self.c = 2.0 * np.sqrt(np.pi) / lam_mm(self.freq_ghz) * 1e-3 * self.scale
        pth, pph = projection_factors(self.theta_deg, self.phi_deg, projection)
        self.pth = torch.as_tensor(pth, dtype=dtype)
        self.pph = torch.as_tensor(pph, dtype=dtype)

        phase = self.k * (self.pos_np @ self.dirs_np.T)      # (N, M)
        chunk = int(chunk_m) if chunk_m else max(self.m, 1)
        self.blocks = []
        self.precompute = bool(precompute)
        for s in range(0, self.m, chunk):
            e = min(s + chunk, self.m)
            blk = {"sl": slice(s, e), "phase_np": phase[:, s:e]}
            if self.precompute:
                ph = torch.as_tensor(phase[:, s:e], dtype=dtype)
                blk["cos"] = torch.cos(ph).T.contiguous()    # (Mc, N)
                blk["sin"] = torch.sin(ph).T.contiguous()
            self.blocks.append(blk)

    # ------------------------------------------------------------------ utils
    @property
    def device(self):
        return self.pth.device

    def to(self, dtype=None, device=None):
        if dtype is not None:
            self.dtype = dtype
            self.pth = self.pth.to(dtype)
            self.pph = self.pph.to(dtype)
        if device is not None:
            self.pth = self.pth.to(device)
            self.pph = self.pph.to(device)
        for blk in self.blocks:
            if "cos" in blk:
                blk["cos"] = blk["cos"].to(dtype=self.dtype, device=self.pth.device)
                blk["sin"] = blk["sin"].to(dtype=self.dtype, device=self.pth.device)
        return self

    def _kernels(self, blk):
        if "cos" in blk:
            return blk["cos"], blk["sin"]
        ph = torch.as_tensor(blk["phase_np"], dtype=self.dtype, device=self.pth.device)
        ph = ph.T.contiguous()
        return torch.cos(ph), torch.sin(ph)

    # ---------------------------------------------------------------- forward
    def __call__(self, q_re, q_im):
        """q_re, q_im: (B, N) -> dict of four (B, M) tensors."""
        if q_re.dim() == 1:
            q_re = q_re.unsqueeze(0)
            q_im = q_im.unsqueeze(0)
        if self.area is not None:
            # equivalent source strength q_n * A_n (B2)
            a = self.area.to(dtype=q_re.dtype, device=q_re.device)
            q_re = q_re * a
            q_im = q_im * a
        outs = {"eth_re": [], "eth_im": [], "eph_re": [], "eph_im": []}
        for blk in self.blocks:
            kc, ks = self._kernels(blk)
            s_re = (q_re @ kc.t() - q_im @ ks.t()) * self.c
            s_im = (q_re @ ks.t() + q_im @ kc.t()) * self.c
            sl = blk["sl"]
            pth = self.pth[sl]
            pph = self.pph[sl]
            outs["eth_re"].append(s_re * pth)
            outs["eth_im"].append(s_im * pth)
            outs["eph_re"].append(s_re * pph)
            outs["eph_im"].append(s_im * pph)
        if len(outs["eth_re"]) == 1:
            return {k: v[0] for k, v in outs.items()}
        return {k: torch.cat(v, dim=1) for k, v in outs.items()}

    # ----------------------------------------------------------------- extras
    def sigma(self, fields: dict):
        return (fields["eth_re"] ** 2 + fields["eth_im"] ** 2
                + fields["eph_re"] ** 2 + fields["eph_im"] ** 2)

    def sigma_db(self, fields: dict, floor_db: float = -300.0):
        return torch.clamp(10.0 * torch.log10(self.sigma(fields).clamp_min(1e-300)),
                           min=floor_db)

    def fields_numpy(self, q) -> Tuple[np.ndarray, np.ndarray]:
        """Convenience wrapper: complex q (B, N) -> complex (B, M) fields."""
        q = np.asarray(q, dtype=complex)
        return farfield_numpy(q, self.theta_deg, self.phi_deg, self.freq_ghz,
                              self.period_mm, self.pos_np, self.projection,
                              self.scale, area_mm2=self.area_np)


def uniform_aperture_dbsm(projection: str = "vector", freq_ghz: float = 10.0,
                          n_side: int = 20, period_mm: float = 14.0,
                          theta_deg=None) -> float:
    """Analytic self-check value at theta = 0 (19.342 dBsm at 10 GHz)."""
    th = np.zeros(1) if theta_deg is None else np.atleast_1d(theta_deg)
    ph = np.zeros_like(th)
    q = np.ones(n_side * n_side, dtype=complex)
    eth, eph = farfield_numpy(q, th, ph, freq_ghz, period_mm,
                              lattice_positions(n_side, period_mm), projection)
    return float(to_db(sigma_from_fields(eth, eph))[0])


if __name__ == "__main__":
    print("plate      : %.4f dBsm" % plate_dbsm())
    print("uniform(sc): %.6f dBsm" % uniform_aperture_dbsm("scalar"))
    print("uniform(vc): %.6f dBsm" % uniform_aperture_dbsm("vector"))
