# -*- coding: utf-8 -*-
"""Local geometry of the array surface: plane and cylinder.

Why this module exists
----------------------
A single scalar normal_z cannot describe a curved array: the network and the
radiation layer need, per node,

    r_n       3-D position                        (already in pos)
    [t1,t2,n] local right-handed frame            (NEW)
    A_n       physical cell area                  (NEW)
    kappa1/2  principal curvatures                (NEW)
    cos_inc   cosine of the local incidence angle (NEW)
    k_t1,k_t2 incidence direction in the local frame (NEW)

so that the local reflection response, the incidence projection and the
far-field phase all refer to the same geometry.  normal_z survives only as the
tilt of the cell against the global z axis (n_hat . z_hat); one number, and it
says nothing about curvature.

Conventions
-----------
* millimetres, right-handed frame with t1 x t2 = n (n points to the
  illuminated / reflection side);
* the incident wave travels along k_hat (energy direction, pointing AT the
  array), so cos_inc = -k_hat . n; cos_inc <= 0 means back-illumination;
* cylinder: x = R sin(u/R), z = -R (1 - cos(u/R)), y = v.  The centre (u=0) is
  the highest point and the surface is convex towards +z, which is the
  illuminated side (cos_inc = +1 there); z <= 0 away from the axis.  u, v are
  arc-length parameters and R -> inf recovers the plane.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

C0_MM_GHZ = 299.792458


def lam_mm(freq_ghz: float) -> float:
    return C0_MM_GHZ / float(freq_ghz)


@dataclass(frozen=True)
class Surface:
    """Parameterised array surface.  kind="plane" is the special case R=inf."""

    kind: str = "plane"
    radius_mm: float = 0.0
    axis: str = "y"

    def check(self) -> "Surface":
        if self.kind not in ("plane", "cylinder"):
            raise ValueError("surface.kind must be plane or cylinder, got %r" % self.kind)
        if self.kind == "cylinder":
            if not np.isfinite(self.radius_mm) or self.radius_mm <= 0:
                raise ValueError("cylinder needs a positive radius_mm")
            if self.axis != "y":
                raise ValueError("only axis=y is implemented")
        return self

    @property
    def is_plane(self) -> bool:
        return self.kind == "plane"

    def grid_uv(self, n_side: int, period_mm: float) -> np.ndarray:
        """(N,2) arc-length parameters (u, v) in mm, centred on the array."""
        a = (np.arange(n_side) - (n_side - 1) / 2.0) * period_mm
        U, V = np.meshgrid(a, a, indexing="ij")
        return np.stack([U.ravel(), V.ravel()], axis=1)

    def positions(self, n_side: int, period_mm: float) -> np.ndarray:
        uv = self.grid_uv(n_side, period_mm)
        u, v = uv[:, 0], uv[:, 1]
        if self.is_plane:
            return np.stack([u, v, np.zeros_like(u)], axis=1)
        th = u / self.radius_mm
        return np.stack([self.radius_mm * np.sin(th),
                         v,
                         -self.radius_mm * (1.0 - np.cos(th))], axis=1)

    def frames(self, n_side: int, period_mm: float) -> np.ndarray:
        """(N,3,3); columns are t1, t2, n (right-handed, t1 x t2 = n)."""
        uv = self.grid_uv(n_side, period_mm)
        u = uv[:, 0]
        n_nodes = u.size
        f = np.zeros((n_nodes, 3, 3))
        if self.is_plane:
            f[:, 0, 0] = 1.0
            f[:, 1, 1] = 1.0
            f[:, 2, 2] = 1.0
            return f
        th = u / self.radius_mm
        # columns are t1, t2, n (audit F1: filling rows here silently transposed
        # the frame, which flipped k_t1 and returned the wrong normal)
        f[:, 0, 0] = np.cos(th)      # t1_x
        f[:, 2, 0] = -np.sin(th)     # t1_z
        f[:, 1, 1] = 1.0             # t2
        f[:, 0, 2] = np.sin(th)      # n_x
        f[:, 2, 2] = np.cos(th)      # n_z
        return f

    def normals(self, n_side: int, period_mm: float) -> np.ndarray:
        return self.frames(n_side, period_mm)[:, :, 2]

    def areas(self, n_side: int, period_mm: float) -> np.ndarray:
        """Physical cell area (mm^2); constant P^2 for the arc-length grid."""
        return np.full(n_side * n_side, period_mm ** 2, dtype=float)

    def curvature(self, n_side: int, period_mm: float) -> np.ndarray:
        """(N,4): kappa1, kappa2, mean H, Gaussian K (units 1/mm)."""
        n = n_side * n_side
        if self.is_plane:
            return np.zeros((n, 4))
        k1 = np.full(n, 1.0 / self.radius_mm)
        k2 = np.zeros(n)
        return np.stack([k1, k2, 0.5 * (k1 + k2), k1 * k2], axis=1)

    def incidence(self, n_side: int, period_mm: float, k_hat=(0.0, 0.0, -1.0)
                  ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (cos_inc, k_t1, k_t2) for an incident wave along k_hat.

        cos_inc = -k_hat . n (> 0 when the cell faces the incoming wave);
        k_t1, k_t2 are the components of k_hat in the local frame -- exactly
        what an angle-dependent unit library needs.
        """
        k = np.asarray(k_hat, dtype=float)
        nrm = np.linalg.norm(k)
        if nrm == 0:
            raise ValueError("k_hat must be non-zero")
        k = k / nrm
        f = self.frames(n_side, period_mm)
        t1, t2, nhat = f[:, :, 0], f[:, :, 1], f[:, :, 2]
        cos_inc = -(nhat @ k)
        return cos_inc, (t1 @ k), (t2 @ k)


def from_config(graph_cfg, physics_cfg=None) -> Optional[Surface]:
    """Build a Surface from the config, or None when geometry features are off."""
    if not getattr(graph_cfg, "geometry", False):
        return None
    kind = str(getattr(graph_cfg, "surface", "plane"))
    radius = float(getattr(graph_cfg, "surface_radius_mm", 0.0))
    surf = Surface(kind=kind, radius_mm=radius).check()
    if surf.is_plane:
        # Audit M3: on a plane every geometry column is constant (cos_inc ==
        # normal_z, k_t2 == 0, A/P^2 == 1), so enabling the block would only add
        # noise and silently change the feature width.  config._validate rejects
        # this combination; returning None keeps the planar path identical.
        return None
    return surf