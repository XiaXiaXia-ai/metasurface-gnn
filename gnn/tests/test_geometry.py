# -*- coding: utf-8 -*-
"""Geometry layer: frames, curvature, incidence, and the opt-in graph block.

Written after the 2026-10-22 audits (F1: the frame was filled by rows but read
by columns).  The decisive check is that t1 equals the analytic derivative of
the positions with respect to u -- t1 x t2 = n and the u=0 values are both
invariant under transposing the frame, so they cannot catch F1.
"""
import numpy as np

import pytest

from msgnn.config import ConfigError, GraphCfg, _validate, load_config
from msgnn.data import geometry as G
from msgnn.data.build_graph import (GEOM_EDGE_FEATURES, GEOM_NODE_FEATURES,
                                    build_graph)
from msgnn.physics.unit_library import UnitLibrary

N, P = 8, 14.0
LAM = 29.9792458


class _FakeCase:
    """The only fields build_graph reads from a Case."""

    def __init__(self, n_side=N, idx=0):
        self.bits = np.ones((n_side, n_side), dtype=np.int8)
        self.idx = idx
        self.name = "fake_%04d" % idx
        self.layout_id = "fake"


def test_plane_is_identity():
    s = G.Surface().check()
    f = s.frames(N, P)
    assert np.allclose(f, np.eye(3)[None], atol=0.0, rtol=0.0)
    assert np.allclose(s.curvature(N, P), 0.0)
    assert np.allclose(s.positions(N, P)[:, 2], 0.0)
    cos_inc, k_t1, k_t2 = s.incidence(N, P)
    assert np.allclose(cos_inc, 1.0)
    assert np.allclose(k_t1, 0.0)
    assert np.allclose(k_t2, 0.0)


def test_cylinder_frame_is_the_position_derivative():
    R = 200.0
    s = G.Surface(kind="cylinder", radius_mm=R).check()
    th = s.grid_uv(N, P)[:, 0] / R
    f = s.frames(N, P)
    t1_ref = np.stack([np.cos(th), np.zeros_like(th), -np.sin(th)], axis=1)
    n_ref = np.stack([np.sin(th), np.zeros_like(th), np.cos(th)], axis=1)
    assert np.allclose(f[:, :, 0], t1_ref, atol=1e-12)   # F1: -sin would fail
    assert np.allclose(f[:, :, 2], n_ref, atol=1e-12)
    assert np.allclose(f[:, :, 1], np.tile([0.0, 1.0, 0.0], (N * N, 1)))
    assert np.allclose(np.cross(f[:, :, 0], f[:, :, 1]), f[:, :, 2], atol=1e-12)
    assert np.allclose(np.linalg.norm(f, axis=1), 1.0, atol=1e-12)
    # discrete step along u (node i -> i+1) must agree with t1 at the midpoint
    pos = s.positions(N, P)
    i_mid = (N // 2) * N
    step = (pos[i_mid + N] - pos[i_mid]) / P
    t1_mid = 0.5 * (f[i_mid, :, 0] + f[i_mid + N, :, 0])
    assert np.allclose(step, t1_mid, atol=2e-3)


def test_cylinder_curvature_and_incidence():
    R = 200.0
    s = G.Surface(kind="cylinder", radius_mm=R).check()
    c = s.curvature(N, P)
    assert np.allclose(c[:, 0], 1.0 / R)
    assert np.allclose(c[:, 1], 0.0)
    assert np.allclose(c[:, 2], 0.5 / R)
    assert np.allclose(c[:, 3], 0.0)
    cos_inc, k_t1, k_t2 = s.incidence(N, P)
    th = s.grid_uv(N, P)[:, 0] / R
    assert np.allclose(cos_inc, np.cos(th), atol=1e-12)   # +1 at u = 0
    assert np.allclose(k_t1, np.sin(th), atol=1e-12)      # F1 returned -sin
    assert np.allclose(k_t2, 0.0)


def test_from_config_guards():
    assert G.from_config(GraphCfg()) is None                     # geometry off
    assert G.from_config(GraphCfg(geometry=True)) is None        # plane: no info
    s = G.from_config(GraphCfg(geometry=True, surface="cylinder",
                              surface_radius_mm=150.0))
    assert isinstance(s, G.Surface) and s.radius_mm == 150.0
    with pytest.raises(Exception):
        G.Surface(kind="cylinder", radius_mm=0.0).check()


def test_config_rejects_plane_geometry():
    c = load_config(None)
    c.graph = GraphCfg(geometry=True, surface="plane")
    with pytest.raises(ConfigError):
        _validate(c)


def test_graph_feature_widths_with_and_without_surface():
    lib = UnitLibrary.floquet(10.0, "floquet")
    case = _FakeCase()
    g0 = build_graph(case, lib, N, P, 1, False, LAM)
    assert g0["x"].shape[1] == 9
    assert g0["edge_attr"].shape[1] == 5
    assert g0["frame"] is None and g0["area"] is None
    s = G.Surface(kind="cylinder", radius_mm=200.0).check()
    g1 = build_graph(case, lib, N, P, 1, False, LAM, surface=s)
    assert g1["x"].shape[1] == 9 + len(GEOM_NODE_FEATURES)
    assert g1["edge_attr"].shape[1] == 5 + len(GEOM_EDGE_FEATURES)
    assert g1["frame"].shape == (N * N, 3, 3)
    assert g1["area"].shape == (N * N,)