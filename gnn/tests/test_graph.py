# -*- coding: utf-8 -*-
"""Graph construction: topology, features, permutation equivariance, batching."""
import os

import numpy as np
import pytest
import torch

from msgnn.config import load_config
from msgnn.data.build_graph import (GraphDataset, build_graph, collate,
                                    edge_index_grid, make_datasets,
                                    neighbour_offsets)
from msgnn.data.dataset import Grid, make_splits, scan_cases
from msgnn.data.normalizer import Normalizer
from msgnn.physics import radiation as R
from msgnn.physics.unit_library import UnitLibrary

DATA = "D:/dataset"
pytestmark = pytest.mark.skipif(not os.path.isdir(DATA),
                                reason="CST dataset not available")


@pytest.fixture(scope="module")
def env():
    cfg = load_config(None)
    grid = Grid.from_step(2.0)
    cases, _ = scan_cases(cfg.data, grid, verbose=False)
    if not cases:
        pytest.skip("no usable cases")
    return cfg, grid, cases, UnitLibrary.floquet(cfg.physics.freq_ghz)


def _graph(cfg, cases, lib, idx=0):
    lam = R.lam_mm(cfg.physics.freq_ghz)
    return build_graph(cases[idx], lib, cfg.physics.n_side, cfg.physics.period_mm,
                       cfg.graph.radius, cfg.graph.self_loops, lam)


def test_edge_offsets():
    assert len(neighbour_offsets(1)) == 8
    assert len(neighbour_offsets(2)) == 24
    assert len(neighbour_offsets(2, self_loops=True)) == 25


def test_edge_index_radius1():
    ei = edge_index_grid(20, 1)
    assert ei.shape == (2, 2964), ei.shape
    assert (ei[0] != ei[1]).all()
    pairs = set(map(tuple, ei.T.tolist()))
    assert len(pairs) == ei.shape[1]
    for a, b in list(pairs)[:400]:
        assert (b, a) in pairs
    deg = np.bincount(ei[1], minlength=400)
    assert deg.max() == 8 and deg.min() == 3
    assert deg.sum() == ei.shape[1]


def test_edge_index_radius2():
    ei = edge_index_grid(20, 2)
    assert len(neighbour_offsets(2)) == 24
    deg = np.bincount(ei[1], minlength=400)
    assert deg.max() == 24
    assert ei.shape[1] == deg.sum()


def test_node_and_edge_features(env):
    cfg, grid, cases, lib = env
    g = _graph(cfg, cases, lib)
    assert g["x"].shape == (400, 9)
    assert np.isfinite(g["x"]).all()
    assert g["edge_attr"].shape == (2964, 5)
    assert np.isfinite(g["edge_attr"]).all()
    # every node must carry one of the two library reflection coefficients
    q0 = g["q0"]
    err = np.minimum(np.abs(q0 - lib.gamma[0]), np.abs(q0 - lib.gamma[1])).max()
    assert err < 1e-5
    near0 = np.abs(q0 - lib.gamma[0]) < 1e-5
    assert near0.sum() == int((g["bits"].ravel() == 0).sum())
    assert g["bits"].shape == (20, 20)
    assert g["pos"].shape == (400, 3)


def test_boundary_flag(env):
    cfg, grid, cases, lib = env
    g = _graph(cfg, cases, lib)
    b = g["x"][:, 7]
    assert b.sum() == 20 * 20 - 18 * 18
    assert g["x"][:, 8].min() == 1.0          # normal_z, planar array


def test_permutation_invariance_operator(env):
    """Relabelling the nodes (weight AND position together) leaves F unchanged.

    The far field is sum_n q_n exp(j k r_n . s), so a node label is only a name:
    the same set of (position, weight) pairs must give the same field.  Permuting
    q alone would of course change it -- that contrapositive is checked too, so the
    test cannot pass by accident.
    """
    cfg, grid, cases, lib = env
    pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
    kw = dict(freq_ghz=cfg.physics.freq_ghz, period_mm=cfg.physics.period_mm,
              projection="vector", dtype=torch.float64)
    op1 = R.FarFieldOperator(grid.theta, grid.phi, pos, **kw)
    rng = np.random.default_rng(0)
    q = rng.normal(size=400) + 1j * rng.normal(size=400)
    perm = rng.permutation(400)
    op2 = R.FarFieldOperator(grid.theta, grid.phi, pos[perm], **kw)
    f1 = op1(torch.tensor(q.real)[None], torch.tensor(q.imag)[None])
    f2 = op2(torch.tensor(q[perm].real)[None], torch.tensor(q[perm].imag)[None])
    for k in f1:
        assert torch.allclose(f1[k], f2[k], rtol=1e-10, atol=1e-12)
    # relabelling the weights without their positions must change the field
    f3 = op1(torch.tensor(q[perm].real)[None], torch.tensor(q[perm].imag)[None])
    assert not torch.allclose(f1["eth_re"], f3["eth_re"], rtol=1e-6)


def test_permutation_equivariance_full_model(env):
    """Relabel the nodes of the graph (and its edges) -> identical far field."""
    cfg, grid, cases, lib = env
    from msgnn.models.pipeline import build_pipeline
    # zero_init_head=False: otherwise the head is exactly zero and the test would
    # pass without exercising the message passing at all
    cfg2 = load_config(None, overrides={"runtime": {"dtype": "float64"},
                                        "model": {"zero_init_head": False}})
    ds = GraphDataset([cases[0]], grid, cfg2, lib, None)
    g = ds.get(0)
    pos = R.lattice_positions(cfg2.physics.n_side, cfg2.physics.period_mm)
    kw = dict(freq_ghz=cfg2.physics.freq_ghz, period_mm=cfg2.physics.period_mm,
              projection="vector", dtype=torch.float64)
    op1 = R.FarFieldOperator(grid.theta, grid.phi, pos, **kw)
    model = build_pipeline(cfg2, 9, 5, grid.n_theta, grid.n_phi, op1)
    model = model.to(torch.float64)
    model.eval()
    from msgnn.experiment import cast_batch
    b1 = cast_batch(collate([g]), torch.float64)
    with torch.no_grad():
        s1 = model(b1)["sig_db"]

    # relabel nodes: features, q0, edges AND the geometry attached to each node
    rng = np.random.default_rng(1)
    perm_np = rng.permutation(400)
    perm = torch.as_tensor(perm_np, dtype=torch.long)
    inv = torch.argsort(perm)
    g2 = dict(g)
    for k in ("x", "q0_re", "q0_im"):
        g2[k] = g[k][perm]
    g2["edge_index"] = inv[g["edge_index"]]
    g2["edge_attr"] = g["edge_attr"]
    op2 = R.FarFieldOperator(grid.theta, grid.phi, pos[perm_np], **kw)
    model2 = build_pipeline(cfg2, 9, 5, grid.n_theta, grid.n_phi, op2)
    model2 = model2.to(torch.float64)
    model2.load_state_dict(model.state_dict())
    model2.eval()
    b2 = cast_batch(collate([g2]), torch.float64)
    with torch.no_grad():
        s2 = model2(b2)["sig_db"]
    assert torch.allclose(s1, s2, rtol=1e-8, atol=1e-10)


def test_collate_keeps_graphs_apart(env):
    cfg, grid, cases, lib = env
    cfg2 = load_config(None)
    ds = GraphDataset(cases[:2], grid, cfg2, lib, None)
    op = R.FarFieldOperator(grid.theta, grid.phi, R.lattice_positions(20, 14.0),
                            10.0, 14.0, "vector", torch.float64)
    b = collate(ds.select([0, 1]))
    for k in ("q0_re", "q0_im"):
        b[k] = b[k].double()
    assert b["n_graphs"] == 2
    assert b["x"].shape[0] == 800
    assert b["edge_index"].max() < 800
    assert b["ptr"].tolist() == [0, 400, 800]
    assert b["batch"][:400].max().item() == 0
    assert b["batch"][400:].min().item() == 1
    # far field of each graph in the batch equals its standalone far field
    f_batch = op(b["q0_re"].view(2, 400), b["q0_im"].view(2, 400))
    for k, i in enumerate((0, 1)):
        g = ds.get(i)
        f_one = op(g["q0_re"].view(1, 400).double(), g["q0_im"].view(1, 400).double())
        for key in f_batch:
            assert torch.allclose(f_batch[key][k], f_one[key][0], rtol=1e-12)


def test_normalizer_fits_train_only(env):
    cfg, grid, cases, lib = env
    ds = GraphDataset(cases[:5], grid, cfg, lib, None)
    graphs = [{"x": g["x"], "edge_attr": g["edge_attr"]} for g in ds.graphs]
    norm = Normalizer.fit(graphs)
    assert norm.n_graphs == 5
    # the statistics are global over the training set, so check the concat of
    # every training graph, and skip columns that carry no variance at all
    # (e.g. normal_z, which is constant 1 for a planar array).
    raw = np.concatenate([g["x"] for g in graphs], 0)
    xt = np.concatenate([norm.transform_x(g["x"]) for g in graphs], 0)
    assert np.abs(xt.mean(0)).max() < 1e-4
    varying = raw.std(0) > 0
    assert np.abs(xt.std(0)[varying] - 1.0).max() < 1e-4
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "n.json")
        norm.save(p)
        n2 = Normalizer.load(p)
    assert np.allclose(n2.x_mean, norm.x_mean)


def test_splits_are_group_disjoint(env):
    cfg, grid, cases, lib = env
    if len(cases) < 10:
        pytest.skip("too few cases")
    sp = make_splits(cases, 0.15, 0.15, seed=1)
    seen = {}
    for k in ("train", "val", "test"):
        for i in sp[k]:
            assert i not in seen
            seen[i] = k
    assert len(seen) == len(cases)
    for g, idxs in sp["groups"].items():
        assert len({seen[i] for i in idxs}) == 1
