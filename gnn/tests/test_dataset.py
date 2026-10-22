# -*- coding: utf-8 -*-
"""Dataset contract, splits, config validation, losses."""
import json
import os

import numpy as np
import pytest
import torch

from msgnn.config import ConfigError, load_config
from msgnn.data.dataset import (Grid, load_complex_case, load_target, make_splits,
                                scan_cases)
from msgnn.losses import ComplexLoss, PowerLoss, angle_weights

DATA = os.environ.get("MSGNN_DATA", "D:/dataset")
HAS_DATA = os.path.isdir(DATA)
needs_data = pytest.mark.skipif(not HAS_DATA, reason="CST dataset not available")


# ------------------------------------------------------------------- grid
def test_grid_2deg():
    g = Grid.from_step(2.0)
    assert g.n_theta == 46 and g.n_phi == 180
    assert g.size == 8280
    assert g.theta[0] == 0.0 and g.theta[-1] == 90.0
    assert g.phi[-1] == 358.0
    assert g.to_grid(np.arange(g.size)).shape == (46, 180)
    m = g.band(6.0, 90.0)
    assert m.sum() == 43 * 180


# ------------------------------------------------------------------- data
@needs_data
def test_scan_cases():
    cfg = load_config(None)
    grid = Grid.from_step(2.0)
    cases, warns = scan_cases(cfg.data, grid, verbose=False)
    assert len(cases) >= 1
    c = cases[0]
    assert c.code10.shape == (10, 10)
    assert c.bits.shape == (20, 20)
    assert c.bits.sum() == c.code10.sum() * cfg.physics.block ** 2
    assert c.layout_id.startswith("L")
    assert os.path.isfile(c.ff_path)
    idxs = [x.idx for x in cases]
    assert idxs == sorted(idxs)


@needs_data
def test_target_matches_metadata():
    cfg = load_config(None)
    grid = Grid.from_step(2.0)
    cases, _ = scan_cases(cfg.data, grid, verbose=False)
    for c in cases[:5]:
        t = load_target(c, grid)
        assert t["sig_db"].shape == (grid.size,)
        assert np.isfinite(t["sig_db"]).all()
        assert np.allclose(10 ** (t["sig_db"] / 10.0),
                           t["eth_mag"] ** 2 + t["eph_mag"] ** 2, rtol=1e-10)
        # specular level recorded in res_XXXX.json is the total sigma at theta = 0
        assert abs(t["sig_db"][0] - c.specular) < 0.01
        # diffuse mean (linear average over theta >= 10 deg) matches as well
        band = grid.theta >= 10.0
        mf = 10 * np.log10((10 ** (t["sig_db"][band] / 10)).mean())
        assert abs(mf - c.mean_far) < 0.02


@needs_data
def test_splits_cover_everything():
    cfg = load_config(None)
    grid = Grid.from_step(2.0)
    cases, _ = scan_cases(cfg.data, grid, verbose=False)
    if len(cases) < 10:
        pytest.skip("too few cases")
    sp = make_splits(cases, 0.15, 0.15, seed=cfg.data.split_seed)
    n = len(cases)
    assert len(sp["train"]) + len(sp["val"]) + len(sp["test"]) == n
    assert abs(len(sp["val"]) / n - 0.15) < 0.05
    assert abs(len(sp["test"]) / n - 0.15) < 0.05
    assert sp["n_groups"] == len(set(c.layout_id for c in cases))
    # deterministic for a fixed seed
    sp2 = make_splits(cases, 0.15, 0.15, seed=cfg.data.split_seed)
    assert sp["train"] == sp2["train"]


@needs_data
def test_complex_export_available():
    cfg = load_config(None)
    if not cfg.data.complex_ff or not os.path.isfile(cfg.data.complex_ff):
        pytest.skip("6-column export not available")
    d = load_complex_case(cfg.data.complex_ff, front_only=True)
    assert d["eth"].shape == d["eph"].shape
    assert np.iscomplexobj(d["eth"])
    assert d["theta"].max() <= 90.0
    assert np.abs(d["eth"]).max() > 1.0
    # same design as case 0000: the amplitude must match the 2 deg export there
    grid = Grid.from_step(2.0)
    cases, _ = scan_cases(cfg.data, grid, verbose=False)
    c0 = [c for c in cases if c.idx == 0]
    if c0:
        t = load_target(c0[0], grid)
        i = int(np.argmin(np.abs(d["theta"] - 0.0) + np.abs(d["phi"] - 0.0)))
        assert abs(10 * np.log10(abs(d["eth"][i]) ** 2 + abs(d["eph"][i]) ** 2)
                   - t["sig_db"][0]) < 0.05


# ---------------------------------------------------------------- config
def test_config_defaults_and_validation():
    cfg = load_config(None)
    assert cfg.model.name == "m3"
    assert cfg.physics.n_side == 20 and cfg.physics.block == 2
    with pytest.raises(ConfigError):
        load_config(None, overrides={"nonsense": 1})
    with pytest.raises(ConfigError):
        load_config(None, overrides={"loss": {"mode": "wrong"}})
    with pytest.raises(ConfigError):
        load_config(None, overrides={"physics": {"n_side": 21, "block": 2}})
    with pytest.raises(ConfigError):
        load_config(None, overrides={"data": {"val_frac": 0.6, "test_frac": 0.6}})


def test_config_roundtrip(tmp_path):
    cfg = load_config(None, overrides={"model": {"hidden": 32, "n_layers": 2},
                                       "optim": {"epochs": 3}})
    p = str(tmp_path / "cfg.yaml")
    cfg.save(p)
    cfg2 = load_config(p)
    assert cfg2.model.hidden == 32 and cfg2.model.n_layers == 2
    assert cfg2.optim.epochs == 3
    assert cfg2.to_dict() == cfg.to_dict()


def test_config_file_parses():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, model in (("train_m3.yaml", "m3"), ("train_m2.yaml", "m2"),
                        ("baseline_m1.yaml", "m1")):
        p = os.path.join(here, "configs", name)
        cfg = load_config(p)
        assert cfg.model.name == model


# ---------------------------------------------------------------- losses
def test_angle_weights():
    th = Grid.from_step(2.0).theta
    cfg = load_config(None).loss
    w = angle_weights(th, cfg)
    assert w.shape == th.shape and (w > 0).all()
    assert w.mean() == pytest.approx(1.0)
    assert w[np.argmin(np.abs(th))] > 0.05        # specular is not weighted out
    cfg2 = load_config(None, overrides={"loss": {"angle_weight": "uniform"}}).loss
    assert np.allclose(angle_weights(th, cfg2), 1.0)


def test_power_loss_zero_and_compression():
    cfg = load_config(None).loss
    th = Grid.from_step(2.0).theta
    loss = PowerLoss(cfg, th)
    t = torch.full((2, th.size), -20.0)
    l0, parts = loss(t.clone(), t)
    assert float(l0) == pytest.approx(0.0, abs=1e-12)
    # a 40 dB error must be compressed well below 40 in the per-point residual
    l1, parts = loss(t + 40.0, t)
    g = float(cfg.compression_db) * np.arcsinh(40.0 / float(cfg.compression_db))
    assert float(l1) == pytest.approx(g * g, rel=1e-5)
    cfg_none = load_config(None, overrides={"loss": {"compression": "none"}}).loss
    l2, _ = PowerLoss(cfg_none, th)(t + 40.0, t)
    assert float(l2) == pytest.approx(1600.0, rel=1e-6)


def test_complex_loss_is_scale_free():
    cfg = load_config(None).loss
    th = Grid.from_step(2.0).theta
    loss = ComplexLoss(cfg, th)
    m = th.size
    targ = {"eth_re": torch.ones(1, m), "eth_im": torch.zeros(1, m),
            "eph_re": torch.zeros(1, m), "eph_im": torch.zeros(1, m)}
    l0, _ = loss(targ, targ)
    assert float(l0) == pytest.approx(0.0, abs=1e-12)
    pred = {k: v * 1.1 for k, v in targ.items()}
    l1, _ = loss(pred, targ)
    # a uniform 10 % amplitude error costs the same everywhere, independent of level
    assert 0.0 < float(l1) < 0.02
