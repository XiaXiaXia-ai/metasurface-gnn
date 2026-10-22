# -*- coding: utf-8 -*-
"""Unit-cell reflection library: state (0/1) -> complex reflection coefficient.

The frozen numbers are the isolated-cell Floquet results at 10 GHz for the
20 x 20 / P = 14 mm / er = 2.65 / h = 1.5 mm design (theory/common.py):

    bit 0 (r = 4.7 mm): 0.867 angle -5.3 deg      |S11| = -1.24 dB
    bit 1 (r = 2.0 mm): 0.852 angle 174.6 deg     |S11| = -1.39 dB
    coding phase difference 179.95 deg

Two amplitude conventions are provided:

    gamma_source='floquet'  the measured/S11 values above (default, faithful)
    gamma_source='unit'     |Gamma| = 1 with the same phases

The second one is not cosmetic: theory/REPORT.md sec. 5.2 shows that the -1.24 dB
of the Floquet run is a numerical (mesh/port) loss, and that the *in-array*
amplitude recovered from the diffuse level of the full-wave data is 1.002.
Models are always reported with the faithful 'floquet' library; 'unit' is offered
so the operator can be checked against the analytic PEC plate and so the residual
1.33 dB offset can be attributed instead of learned.

Angle dependence
----------------
Normal incidence is the only characterised condition, so the default library is
angle independent.  UnitLibrary.from_csv loads a table
    state,theta_deg,phi_deg,re,im
and performs bilinear (theta, phi) interpolation, which is the extension point
required for oblique incidence (plan step 02).  Out of range queries are clamped
AND flagged (return_oob) rather than silently extrapolated.
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

GAMMA_ABS = (0.867, 0.852)
GAMMA_PH_DEG = (-5.3, 174.6)

C0_MM_GHZ = 299.792458


def floquet_gamma(freq_ghz: float = 10.0, gamma_source: str = "floquet") -> np.ndarray:
    """(2,) complex reflection coefficients for bit 0 / bit 1."""
    if gamma_source not in ("floquet", "unit"):
        raise ValueError("gamma_source must be 'floquet' or 'unit', got %r" % (gamma_source,))
    absg = GAMMA_ABS if gamma_source == "floquet" else (1.0, 1.0)
    return np.array([a * np.exp(1j * np.radians(p))
                     for a, p in zip(absg, GAMMA_PH_DEG)], dtype=complex)


def coding_phase_deg(gamma: Optional[np.ndarray] = None) -> float:
    """Phase difference bit1 - bit0, wrapped into [0, 360)."""
    g = floquet_gamma() if gamma is None else np.asarray(gamma)
    return float(np.degrees(np.angle(g[1] / g[0])) % 360.0)


@dataclass
class UnitLibrary:
    """state -> complex reflection, optionally angle dependent."""

    gamma: np.ndarray = field(default_factory=floquet_gamma)
    freq_ghz: float = 10.0
    theta_ax: Optional[np.ndarray] = None       # (nth,) deg, ascending
    phi_ax: Optional[np.ndarray] = None         # (nph,) deg, ascending
    table: Optional[np.ndarray] = None          # (2, nth, nph) complex
    source: str = "floquet"

    # ------------------------------------------------------------------ ctors
    @classmethod
    def floquet(cls, freq_ghz: float = 10.0, gamma_source: str = "floquet") -> "UnitLibrary":
        return cls(gamma=floquet_gamma(freq_ghz, gamma_source), freq_ghz=freq_ghz,
                   source=gamma_source)

    @classmethod
    def from_csv(cls, path: str, freq_ghz: float = 10.0) -> "UnitLibrary":
        d = np.loadtxt(path, delimiter=",", skiprows=1)
        states = np.unique(d[:, 0]).astype(int)
        if list(states) != [0, 1]:
            raise ValueError("%s: expected states 0 and 1, got %s" % (path, states))
        th = np.unique(d[:, 1])
        ph = np.unique(d[:, 2])
        tab = np.zeros((2, th.size, ph.size), dtype=complex)
        it = {v: i for i, v in enumerate(th)}
        ip = {v: i for i, v in enumerate(ph)}
        for s, t, p, re, im in d:
            tab[int(s), it[t], ip[p]] = re + 1j * im
        g = tab[:, 0, 0]
        return cls(gamma=g, freq_ghz=freq_ghz, theta_ax=th, phi_ax=ph, table=tab,
                   source=os.path.basename(path))

    # ------------------------------------------------------------------ query
    @property
    def angle_dependent(self) -> bool:
        return self.table is not None

    def pair(self) -> Tuple[complex, complex]:
        return complex(self.gamma[0]), complex(self.gamma[1])

    def __call__(self, state, theta_deg=None, phi_deg=None, return_oob: bool = False):
        """state (array of 0/1) -> complex Gamma.

        theta_deg / phi_deg are optional and only used when a table is loaded.
        """
        s = np.asarray(state).astype(int)
        if s.size and (s.min() < 0 or s.max() > 1):
            raise ValueError("state must be 0/1")
        if self.table is None or theta_deg is None:
            out = self.gamma[s]
            if return_oob:
                return out, np.zeros(s.shape, dtype=bool)
            return out

        th = np.atleast_1d(np.asarray(theta_deg, dtype=float))
        ph = np.atleast_1d(np.asarray(phi_deg if phi_deg is not None else 0.0,
                                      dtype=float))
        th, ph = np.broadcast_arrays(th, ph)
        nth, nph = self.theta_ax.size, self.phi_ax.size
        oob = ((th < self.theta_ax[0]) | (th > self.theta_ax[-1])
               | (ph < self.phi_ax[0]) | (ph > self.phi_ax[-1]))
        thc = np.clip(th, self.theta_ax[0], self.theta_ax[-1])
        phc = np.clip(ph, self.phi_ax[0], self.phi_ax[-1])
        i0 = np.clip(np.searchsorted(self.theta_ax, thc, side="right") - 1, 0, nth - 2)
        j0 = np.clip(np.searchsorted(self.phi_ax, phc, side="right") - 1, 0, nph - 2)
        ft = (thc - self.theta_ax[i0]) / np.maximum(
            self.theta_ax[i0 + 1] - self.theta_ax[i0], 1e-12)
        fp = (phc - self.phi_ax[j0]) / np.maximum(
            self.phi_ax[j0 + 1] - self.phi_ax[j0], 1e-12)
        ft = np.clip(ft, 0.0, 1.0)
        fp = np.clip(fp, 0.0, 1.0)
        sb = np.broadcast_to(s, th.shape)
        t = self.table
        g = ((1 - ft) * (1 - fp) * t[sb, i0, j0] + ft * (1 - fp) * t[sb, i0 + 1, j0]
             + (1 - ft) * fp * t[sb, i0, j0 + 1] + ft * fp * t[sb, i0 + 1, j0 + 1])
        if return_oob:
            return g, oob
        return g
