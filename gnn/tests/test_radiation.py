# -*- coding: utf-8 -*-
"""Radiation layer: PEC-plate self-check, torch vs numpy, theory cross-check, gradients."""
import os
import sys

import numpy as np
import pytest
import torch

from msgnn.physics import radiation as R

THEORY = r"D:/GNN/theory"


def grid2(theta_max=90.0, step=2.0):
    th = np.arange(0.0, theta_max + 1e-9, step)
    ph = np.arange(0.0, 360.0 - 1e-9, step)
    T, P = np.meshgrid(th, ph, indexing="ij")
    return T.ravel(), P.ravel()


def test_plate_value():
    assert R.plate_dbsm(10.0) == pytest.approx(19.342, abs=1e-3)
    assert R.const_c(10.0) == pytest.approx(2 * np.sqrt(np.pi) / 29.9792458 * 196 * 1e-3,
                                            rel=1e-9)


@pytest.mark.parametrize("mode", ["scalar", "vector"])
def test_uniform_aperture_is_pec_plate(mode):
    th = np.array([0.0, 0.0, 0.0])
    ph = np.array([0.0, 90.0, 210.0])
    pos = R.lattice_positions(20, 14.0)
    op = R.FarFieldOperator(th, ph, pos, 10.0, 14.0, mode, torch.float64)
    qr = torch.ones(1, pos.shape[0], dtype=torch.float64)
    qi = torch.zeros(1, pos.shape[0], dtype=torch.float64)
    db = op.sigma_db(op(qr, qi)).numpy()
    assert np.allclose(db, R.plate_dbsm(10.0), atol=1e-6), db


def test_uniform_aperture_numpy():
    th = np.zeros(1)
    ph = np.zeros(1)
    q = np.ones(400, dtype=complex)
    eth, eph = R.farfield_numpy(q, th, ph, 10.0, 14.0)
    sig = R.sigma_from_fields(eth, eph)
    assert R.to_db(sig)[0] == pytest.approx(19.342, abs=1e-6)


@pytest.mark.parametrize("mode", ["scalar", "vector"])
def test_torch_matches_numpy(mode):
    rng = np.random.default_rng(0)
    th = np.concatenate([np.zeros(1), rng.uniform(0, 90, 60)])
    ph = np.concatenate([np.zeros(1), rng.uniform(0, 360, 60)])
    pos = R.lattice_positions(20, 14.0)
    q = rng.normal(size=400) + 1j * rng.normal(size=400)
    e_ref, p_ref = R.farfield_numpy(q, th, ph, 10.0, 14.0, pos, mode)
    op = R.FarFieldOperator(th, ph, pos, 10.0, 14.0, mode, torch.float64)
    f = op(torch.tensor(q.real)[None], torch.tensor(q.imag)[None])
    e = (f["eth_re"][0].numpy() + 1j * f["eth_im"][0].numpy())
    p = (f["eph_re"][0].numpy() + 1j * f["eph_im"][0].numpy())
    norm = max(np.abs(e_ref).max(), np.abs(p_ref).max(), 1e-30)
    assert np.max(np.abs(e - e_ref)) / norm < 1e-6
    assert np.max(np.abs(p - p_ref)) / norm < 1e-6


def test_projection_vector_polarisation():
    th = np.array([0.0, 45.0, 45.0])
    ph = np.array([0.0, 0.0, 90.0])
    pth, pph = R.projection_factors(th, ph, "vector")
    assert pth[0] == pytest.approx(1.0)
    assert pph[0] == pytest.approx(0.0)
    # 45 deg: E-plane keeps cos(theta), H-plane has no cos(theta) factor
    assert pth[1] == pytest.approx(np.cos(np.radians(45)))
    assert abs(pph[1]) < 1e-12
    assert abs(pth[2]) < 1e-12
    assert pph[2] == pytest.approx(-1.0)


def test_theta_zero_is_phi_independent():
    pos = R.lattice_positions(20, 14.0)
    rng = np.random.default_rng(1)
    q = rng.normal(size=400) + 1j * rng.normal(size=400)
    th = np.zeros(5)
    ph = np.linspace(0, 300, 5)
    eth, eph = R.farfield_numpy(q, th, ph, 10.0, 14.0, pos, "vector")
    sig = R.sigma_from_fields(eth, eph)
    assert np.allclose(sig, sig[0], rtol=1e-12)


def test_matches_theory_models():
    if not os.path.isfile(os.path.join(THEORY, "models.py")):
        pytest.skip("theory/models.py not available")
    sys.path.insert(0, THEORY)
    try:
        import common as C
        import models as M
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip("theory package unimportable: %s" % exc)
    th, ph = grid2()
    g = C.Grid(th, ph)
    cm, _ = C.base_code_map()
    for proj in ("scalar", "vector"):
        ref = M.af_ideal(g, 10.0, cm, projection=proj)
        q = C.gamma_map(cm).ravel()
        eth, eph = R.farfield_numpy(q, th, ph, 10.0, 14.0,
                                    R.lattice_positions(20, 14.0), proj)
        scale = np.maximum(np.abs(ref.eth), 1e-30)
        assert np.max(np.abs(eth - ref.eth) / scale) < 1e-9
        assert np.max(np.abs(eph - ref.eph) / scale) < 1e-9


def test_gradients_match_finite_differences():
    rng = np.random.default_rng(2)
    pos = R.lattice_positions(4, 14.0)
    th = rng.uniform(5, 70, 25)
    ph = rng.uniform(0, 360, 25)
    op = R.FarFieldOperator(th, ph, pos, 10.0, 14.0, "vector", torch.float64)
    q0 = rng.normal(size=pos.shape[0]) + 1j * rng.normal(size=pos.shape[0])
    qr = torch.tensor(q0.real.copy(), dtype=torch.float64, requires_grad=True)
    qi = torch.tensor(q0.imag.copy(), dtype=torch.float64, requires_grad=True)
    loss = op.sigma(op(qr[None], qi[None])).sum()
    loss.backward()
    h = 1e-6
    for i in range(pos.shape[0]):
        d = np.zeros(pos.shape[0], dtype=complex)
        d[i] = h
        f1 = R.sigma_from_fields(*R.farfield_numpy(q0 + d, th, ph, 10.0, 14.0, pos,
                                                   "vector")).sum()
        f2 = R.sigma_from_fields(*R.farfield_numpy(q0 - d, th, ph, 10.0, 14.0, pos,
                                                   "vector")).sum()
        num_re = (f1 - f2) / (2 * h)
        assert qr.grad[i].item() == pytest.approx(num_re, rel=1e-5)
        d[i] = 1j * h
        f1 = R.sigma_from_fields(*R.farfield_numpy(q0 + d, th, ph, 10.0, 14.0, pos,
                                                   "vector")).sum()
        f2 = R.sigma_from_fields(*R.farfield_numpy(q0 - d, th, ph, 10.0, 14.0, pos,
                                                   "vector")).sum()
        num_im = (f1 - f2) / (2 * h)
        assert qi.grad[i].item() == pytest.approx(num_im, rel=1e-5)


def test_batch_matches_single():
    rng = np.random.default_rng(3)
    pos = R.lattice_positions(20, 14.0)
    th, ph = grid2()
    op = R.FarFieldOperator(th, ph, pos, 10.0, 14.0, "vector", torch.float64)
    q = rng.normal(size=(3, 400)) + 1j * rng.normal(size=(3, 400))
    f = op(torch.tensor(q.real), torch.tensor(q.imag))
    for b in range(3):
        fb = op(torch.tensor(q[b].real)[None], torch.tensor(q[b].imag)[None])
        for k in f:
            assert torch.allclose(f[k][b], fb[k][0], rtol=1e-12, atol=1e-15)


def test_solid_angle_weights():
    th, _ = grid2()
    w = R.solid_angle_weights(th, floor=0.05)
    assert w.shape == th.shape
    assert w.mean() == pytest.approx(1.0)
    assert (w > 0).all()
