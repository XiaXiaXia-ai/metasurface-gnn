# -*- coding: utf-8 -*-
"""Local-periodic baseline (M0) and the oracle global-scalar reference.

M0 is the model that theory/REPORT.md calls M0: every node carries the isolated
cell Floquet reflection coefficient, and the operator above turns those weights
into a vector far field.  It has no free parameter, so "training M0" does not
exist -- it is evaluated directly.

The physics established on this data (theory/REPORT.md sec. 5) says that M0 is
excellent on the diffuse structure but misses the specular lobe by ~13.8 dB,
because the array carries a code-orthogonal *uniform common mode* b with
|b| ~ 0.37.  Two consequences are implemented here:

  * M3 may add a per-sample complex scalar b learned from the code (the GNN
    global branch), which is the parameterisation recommended by the report;
  * to know how much of the gap a *single complex scalar per sample* can close,
    fit_global_scalar fits b directly on the label.  That is an oracle (it uses
    the target, 2 real parameters per sample) and it is reported as an upper
    reference for "global scalar only", never as a predictive model.
"""
from typing import Optional, Tuple

import numpy as np

from . import radiation as R
from .unit_library import UnitLibrary


def q0_from_bits(bits, library: UnitLibrary, theta_deg=None, phi_deg=None) -> np.ndarray:
    """Physical (20x20) 0/1 map -> complex per-node weight q0 (N,)."""
    return np.asarray(library(np.asarray(bits).ravel(), theta_deg, phi_deg), dtype=complex)


def baseline_fields(bits, theta_deg, phi_deg, library: UnitLibrary,
                    freq_ghz: float = 10.0, period_mm: float = 14.0,
                    projection: str = "vector", pos_mm: Optional[np.ndarray] = None
                    ) -> Tuple[np.ndarray, np.ndarray]:
    q0 = q0_from_bits(bits, library)
    return R.farfield_numpy(q0, theta_deg, phi_deg, freq_ghz, period_mm, pos_mm,
                            projection)


def baseline_sigma_db(bits, theta_deg, phi_deg, **kw) -> np.ndarray:
    eth, eph = baseline_fields(bits, theta_deg, phi_deg, **kw)
    return R.to_db(R.sigma_from_fields(eth, eph))


# --------------------------------------------------------------- oracle fit
def _db_residual(a_abs2, target_db, w, floor_db=-60.0):
    p = np.maximum(10.0 * np.log10(np.maximum(a_abs2, 1e-300)), floor_db)
    r = p - target_db
    return float(np.sum(w * r * r)), p


def fit_global_scalar(g0: np.ndarray, gu: np.ndarray, target_db: np.ndarray,
                      w: Optional[np.ndarray] = None, starts: int = 3,
                      iters: int = 220, lr: float = 0.08,
                      floor_db: float = -60.0) -> Tuple[complex, np.ndarray, float]:
    """Fit one complex scalar b minimising sum w (10log10|g0 + b gu|^2 - t)^2.

    g0, gu : complex (M,) fields of the baseline and of the uniform (all-ones)
             aperture on the same angle grid, already including the projection.
    Returns (b, predicted_db, weighted_rmse).
    """
    g0 = np.asarray(g0, dtype=complex).ravel()
    gu = np.asarray(gu, dtype=complex).ravel()
    t = np.asarray(target_db, dtype=float).ravel()
    if w is None:
        w = np.ones_like(t)
    w = np.asarray(w, dtype=float).ravel()
    w = w / w.sum()
    ln10 = np.log(10.0)

    # coarse grid: the optimum is close to a circle of radius ~0.4 in the
    # (Re b, Im b) plane, so a modest polargrid is enough to bracket it.
    best = None
    rad = np.linspace(0.0, 1.2, 13)
    ang = np.linspace(0.0, 2 * np.pi, 12, endpoint=False)
    for rr in rad:
        for aa in ang:
            b = rr * np.exp(1j * aa)
            a2 = np.abs(g0 + b * gu) ** 2
            f, _ = _db_residual(a2, t, w, floor_db)
            if best is None or f < best[0]:
                best = (f, b)
    cands = [best[1]]
    for k in range(1, max(starts, 1)):
        cands.append(0.4 * np.exp(2j * np.pi * k / max(starts, 1) + 0.7))

    out = None
    for b0 in cands:
        b = complex(b0)
        m = np.zeros(2)
        v = np.zeros(2)
        f_prev = None
        for it in range(1, iters + 1):
            a = g0 + b * gu
            a2 = np.abs(a) ** 2
            f, p = _db_residual(a2, t, w, floor_db)
            r = p - t
            # dp/db_re = (10/ln10) 2 Re(A* gu)/|A|^2
            # dp/db_im = -(10/ln10) 2 Im(A* gu)/|A|^2   (the j from dA/db_im)
            dp = (10.0 / ln10) * 2.0 * (np.conj(a) * gu) / np.maximum(a2, 1e-300)
            grad = np.array([2.0 * np.sum(w * r * np.real(dp)),
                             -2.0 * np.sum(w * r * np.imag(dp))])
            # Adam on a 2-D problem is stable and needs no line search
            m = 0.9 * m + 0.1 * grad
            v = 0.999 * v + 0.001 * grad * grad
            mh = m / (1 - 0.9 ** it)
            vh = v / (1 - 0.999 ** it)
            step = lr * mh / (np.sqrt(vh) + 1e-12)
            b = b - complex(step[0], step[1])
            if f_prev is not None and abs(f_prev - f) < 1e-12:
                break
            f_prev = f
        a2 = np.abs(g0 + b * gu) ** 2
        f, p = _db_residual(a2, t, w, floor_db)
        if out is None or f < out[0]:
            out = (f, b, p)
    f, b, p = out
    rmse = float(np.sqrt(f))
    return b, p, rmse


def field_terms(bits, theta_deg, phi_deg, library: UnitLibrary,
                freq_ghz: float = 10.0, period_mm: float = 14.0,
                projection: str = "vector", pos_mm: Optional[np.ndarray] = None
                ) -> Tuple[np.ndarray, np.ndarray]:
    """(g0, gu): complex far-field samples of the q0 aperture and of the uniform
    (all-ones) aperture, both already carrying the projection factor.

    sigma(b) = |g0 + b * gu|^2 for the 'baseline + complex global scalar' model.
    """
    q0 = q0_from_bits(bits, library)
    ones = np.ones_like(q0)
    s0 = R.aperture_sum_numpy(q0, theta_deg, phi_deg, freq_ghz, period_mm, pos_mm)
    su = R.aperture_sum_numpy(ones, theta_deg, phi_deg, freq_ghz, period_mm, pos_mm)
    pth, pph = R.projection_factors(theta_deg, phi_deg, projection)
    peff = np.sqrt(pth ** 2 + pph ** 2)
    c = R.const_c(freq_ghz, period_mm)
    return c * s0 * peff, c * su * peff
