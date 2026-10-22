# -*- coding: utf-8 -*-
"""code -> graph: nodes are unit cells, edges are the 8 (or 24) surface neighbours.

Node features (fixed order, see NODE_FEATURES)
    0 bit            0/1 coding state
    1 bit_signed     2*bit-1, so a single linear layer can separate the two states
    2 x/lambda       position along x, in wavelengths
    3 y/lambda       position along y, in wavelengths
    4 Re Gamma       local reflection coefficient (real part)
    5 Im Gamma       local reflection coefficient (imag part)
    6 |Gamma|
    7 boundary       1 on the array rim (edge coupling / truncation proxy)
    8 normal_z       n_hat . z_hat  (= 1 for the planar array).  One number is
                     NOT enough for a curved surface: with graph.geometry=true
                     GEOM_NODE_FEATURES appends cos_inc, k_t1, k_t2, kappa1*lam,
                     kappa2*lam and A/P^2 from data/geometry.py

Edge features (both directions are inserted, directed edges)
    0 dx/lambda, 1 dy/lambda, 2 r/lambda, 3 cos(azimuth), 4 sin(azimuth)
    NOTE dx/dy/r/azimuth are the *projected* (x-y) values.  On a curved surface
    they differ from the true 3-D separation, which is why the geometry block
    appends r3d/lambda as a separate column.

Geometry used by the physics (positions in mm, q0, the target) is stored raw and
is never normalised.  Node reordering leaves the far field unchanged because the
operator only sums over nodes -- tested in tests/test_graph.py.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from ..config import Config
from ..physics import radiation as R
from ..physics.unit_library import UnitLibrary
from . import geometry as G
from .dataset import Case, Grid, load_target
from .normalizer import Normalizer

NODE_FEATURES = ("bit", "bit_signed", "x_lam", "y_lam", "gamma_re", "gamma_im",
                 "gamma_abs", "boundary", "normal_z")
# appended only when a Surface is supplied (graph.geometry = true)
GEOM_NODE_FEATURES = ("cos_inc", "k_t1", "k_t2", "kappa1_lam", "kappa2_lam",
                      "area_ratio")
EDGE_FEATURES = ("dx_lam", "dy_lam", "r_lam", "cos_az", "sin_az")
GEOM_EDGE_FEATURES = ("r3d_lam", "normal_mismatch")


# ---------------------------------------------------------------- primitives
def lattice_xy(n_side: int, period_mm: float) -> np.ndarray:
    x = (np.arange(n_side) - (n_side - 1) / 2.0) * period_mm
    X, Y = np.meshgrid(x, x, indexing="ij")
    return np.stack([X.ravel(), Y.ravel()], axis=1)


def neighbour_offsets(radius: int, self_loops: bool = False) -> List[Tuple[int, int]]:
    out = []
    for di in range(-radius, radius + 1):
        for dj in range(-radius, radius + 1):
            if di == 0 and dj == 0 and not self_loops:
                continue
            out.append((di, dj))
    return out


def edge_index_grid(n_side: int, radius: int = 1,
                    self_loops: bool = False) -> np.ndarray:
    """(2, E) directed edges (source, target) for a periodic-free square lattice."""
    idx = np.arange(n_side * n_side).reshape(n_side, n_side)
    src, dst = [], []
    for di, dj in neighbour_offsets(radius, self_loops):
        i0, i1 = max(0, -di), min(n_side, n_side - di)
        j0, j1 = max(0, -dj), min(n_side, n_side - dj)
        if i0 >= i1 or j0 >= j1:
            continue
        a = idx[i0:i1, j0:j1]                 # centre
        b = idx[i0 + di:i1 + di, j0 + dj:j1 + dj]   # neighbour
        dst.append(a.ravel())
        src.append(b.ravel())
    e = np.stack([np.concatenate(src), np.concatenate(dst)], axis=0).astype(np.int64)
    order = np.lexsort((e[1], e[0]))
    return e[:, order]


def node_features(bits: np.ndarray, pos_xy: np.ndarray, gamma: np.ndarray,
                  n_side: int, period_mm: float, lam: float,
                  normal_z: Optional[np.ndarray] = None,
                  geom: Optional[dict] = None) -> np.ndarray:
    b = np.asarray(bits, dtype=np.float64).ravel()
    n = b.size
    ii = np.arange(n) // n_side
    jj = np.arange(n) % n_side
    boundary = ((ii == 0) | (ii == n_side - 1) | (jj == 0) | (jj == n_side - 1))
    nz = np.ones(n) if normal_z is None else np.asarray(normal_z, dtype=np.float64)
    g = np.asarray(gamma, dtype=complex).ravel()
    cols = [b, 2.0 * b - 1.0,
            pos_xy[:, 0] / lam, pos_xy[:, 1] / lam,
            g.real, g.imag, np.abs(g),
            boundary.astype(np.float64), nz]
    if geom is not None:
        # geometry block (GEOM_NODE_FEATURES order): a curved array needs the
        # local frame and curvature, not just n_hat . z_hat.
        cols += [np.asarray(geom["cos_inc"], dtype=np.float64),
                 np.asarray(geom["k_t1"], dtype=np.float64),
                 np.asarray(geom["k_t2"], dtype=np.float64),
                 np.asarray(geom["kappa1"], dtype=np.float64) * lam,
                 np.asarray(geom["kappa2"], dtype=np.float64) * lam,
                 np.asarray(geom["area_ratio"], dtype=np.float64)]
    x = np.stack(cols, axis=1)
    return x.astype(np.float32)


def edge_features(edge_index: np.ndarray, pos_xy: np.ndarray, lam: float) -> np.ndarray:
    src, dst = edge_index[0], edge_index[1]
    dx = (pos_xy[dst, 0] - pos_xy[src, 0]) / lam
    dy = (pos_xy[dst, 1] - pos_xy[src, 1]) / lam
    r = np.hypot(dx, dy)
    az = np.arctan2(dy, dx)
    return np.stack([dx, dy, r, np.cos(az), np.sin(az)], axis=1).astype(np.float32)


def build_graph(case: Case, library: UnitLibrary, n_side: int, period_mm: float,
                radius: int, self_loops: bool, lam: float,
                edge_features_on: bool = True,
                surface: Optional["G.Surface"] = None) -> dict:
    if case.bits.size != n_side * n_side:
        raise ValueError("%s: %d bits != %d nodes" % (case.name, case.bits.size,
                                                      n_side * n_side))
    if surface is not None:
        surface.check()          # S3: a radius=0 cylinder would produce NaNs
    gamma = library(case.bits.ravel())
    if surface is None:
        pos_xy = lattice_xy(n_side, period_mm)
        pos = np.concatenate([pos_xy, np.zeros((pos_xy.shape[0], 1))], axis=1)
        normal_z, geom, frames, areas, curv = None, None, None, None, None
    else:
        pos = surface.positions(n_side, period_mm)
        frames = surface.frames(n_side, period_mm)
        areas = surface.areas(n_side, period_mm)
        curv = surface.curvature(n_side, period_mm)
        cos_inc, k_t1, k_t2 = surface.incidence(n_side, period_mm)
        pos_xy = pos[:, :2]
        normal_z = frames[:, 2, 2]
        geom = dict(cos_inc=cos_inc, k_t1=k_t1, k_t2=k_t2,
                    kappa1=curv[:, 0], kappa2=curv[:, 1],
                    area_ratio=areas / (period_mm ** 2))
    x = node_features(case.bits, pos_xy, gamma, n_side, period_mm, lam,
                      normal_z=normal_z, geom=geom)
    ei = edge_index_grid(n_side, radius, self_loops)
    ea = (edge_features(ei, pos_xy, lam) if edge_features_on
          else np.zeros((ei.shape[1], 0), dtype=np.float32))
    if surface is not None and edge_features_on:
        # geometric edge block: true 3-D separation and the local normal change
        # across the edge (a curvature proxy the 2-D features cannot see).
        src, dst = ei[0], ei[1]
        d3 = np.linalg.norm(pos[dst] - pos[src], axis=1) / lam
        mism = 1.0 - np.sum(frames[src, :, 2] * frames[dst, :, 2], axis=1)
        ea = np.concatenate([ea, np.stack([d3, mism], axis=1).astype(np.float32)], axis=1)
    return {"x": x, "edge_index": ei, "edge_attr": ea, "pos": pos.astype(np.float32),
            "q0": np.asarray(gamma, dtype=np.complex64),
            "q0_re": np.asarray(np.real(gamma), dtype=np.float32),
            "q0_im": np.asarray(np.imag(gamma), dtype=np.float32),
            "bits": np.asarray(case.bits, dtype=np.float32),
            "frame": (None if frames is None else frames.astype(np.float32)),
            "area": (None if areas is None else areas.astype(np.float32)),
            "curv": (None if curv is None else curv.astype(np.float32)),
            "case_idx": int(case.idx), "name": case.name,
            "layout_id": case.layout_id,
            "n_nodes": int(x.shape[0]), "n_edges": int(ei.shape[1])}


# ------------------------------------------------------------------- dataset
class GraphDataset:
    """All graphs + targets in RAM, with per-split normalisation statistics."""

    def __init__(self, cases: Sequence[Case], grid: Grid, cfg: Config,
                 library: UnitLibrary, norm: Optional[Normalizer] = None):
        self.cases = list(cases)
        self.grid = grid
        self.cfg = cfg
        self.library = library
        self.lam = R.lam_mm(cfg.physics.freq_ghz)
        # geometry features are opt-in (graph.geometry); None keeps the planar
        # path bit-for-bit identical to the pre-2026-10-22 behaviour.
        self.surface = G.from_config(cfg.graph)
        self.graphs: List[dict] = []
        for c in self.cases:
            self.graphs.append(build_graph(
                c, library, cfg.physics.n_side, cfg.physics.period_mm,
                cfg.graph.radius, cfg.graph.self_loops, self.lam,
                cfg.graph.edge_features, surface=self.surface))
        self.by_idx = {g["case_idx"]: i for i, g in enumerate(self.graphs)}
        tgt = np.stack([load_target(c, grid)["sig_db"] for c in self.cases], axis=0)
        self.target_db = torch.as_tensor(tgt.astype(np.float32))
        self.specular = torch.as_tensor(tgt[:, 0].astype(np.float32))
        self.norm = norm
        if norm is not None:
            for g in self.graphs:
                g["x"] = norm.transform_x(g["x"])
                g["edge_attr"] = norm.transform_e(g["edge_attr"])

    # ------------------------------------------------------------------ access
    def __len__(self) -> int:
        return len(self.graphs)

    def index_of(self, case_idx: int) -> int:
        return self.by_idx[int(case_idx)]

    def get(self, i: int) -> dict:
        g = self.graphs[i]
        out = dict(g)
        out["x"] = torch.as_tensor(g["x"], dtype=torch.float32)
        out["edge_index"] = torch.as_tensor(g["edge_index"], dtype=torch.long)
        out["edge_attr"] = torch.as_tensor(g["edge_attr"], dtype=torch.float32)
        out["pos"] = torch.as_tensor(g["pos"], dtype=torch.float32)
        out["q0"] = torch.as_tensor(g["q0"].astype(np.complex128))
        out["q0_re"] = torch.as_tensor(g["q0_re"], dtype=torch.float32)
        out["q0_im"] = torch.as_tensor(g["q0_im"], dtype=torch.float32)
        out["bits"] = torch.as_tensor(g["bits"], dtype=torch.float32)
        out["sig_db"] = self.target_db[i]
        return out

    def select(self, indices: Sequence[int]) -> List[dict]:
        return [self.get(i) for i in indices]


def collate(graphs: Sequence[dict], pin: bool = False) -> dict:
    """Concatenate graphs into one disjoint batch (no PyG needed)."""
    xs, eis, eas, qs, qr, qi, ptr = [], [], [], [], [], [], [0]
    batches = []
    for k, g in enumerate(graphs):
        n = g["x"].shape[0]
        xs.append(g["x"])
        ei = g["edge_index"]
        eis.append(ei + ptr[-1])
        if g["edge_attr"].numel():
            eas.append(g["edge_attr"])
        qs.append(g["q0"])
        qr.append(g["q0_re"])
        qi.append(g["q0_im"])
        batches.append(torch.full((n,), k, dtype=torch.long))
        ptr.append(ptr[-1] + n)
    x = torch.cat(xs, 0)
    edge_index = torch.cat(eis, 1) if eis else torch.zeros((2, 0), dtype=torch.long)
    edge_attr = (torch.cat(eas, 0) if eas
                 else torch.zeros((edge_index.shape[1], 0), dtype=torch.float32))
    q0 = torch.cat(qs, 0)
    out = {"x": x, "edge_index": edge_index, "edge_attr": edge_attr,
           "q0": q0, "q0_re": torch.cat(qr, 0), "q0_im": torch.cat(qi, 0),
           "batch": torch.cat(batches), "ptr": torch.tensor(ptr),
           "n_graphs": len(graphs),
           "bits": torch.stack([g["bits"] for g in graphs], 0),
           "case_idx": [g["case_idx"] for g in graphs],
           "sig_db": torch.stack([g["sig_db"] for g in graphs], 0)}
    return out


def make_datasets(cfg: Config, cases: Sequence[Case], grid: Grid,
                  splits: dict, library: Optional[UnitLibrary] = None,
                  max_train: int = 0
                  ) -> Tuple[GraphDataset, GraphDataset, GraphDataset, Normalizer]:
    """Build train/val/test datasets; the normaliser sees the training graphs only.

    max_train > 0 truncates the TRAIN split (used by the smoke test and by the
    data-efficiency curve); val/test are never truncated.
    """
    if library is None:
        library = UnitLibrary.floquet(cfg.physics.freq_ghz, cfg.physics.gamma_source)
    tr_idx = [i for i, c in enumerate(cases) if c.idx in set(splits["train"])]
    if max_train and len(tr_idx) > int(max_train):
        tr_idx = tr_idx[:int(max_train)]
    va_idx = [i for i, c in enumerate(cases) if c.idx in set(splits["val"])]
    te_idx = [i for i, c in enumerate(cases) if c.idx in set(splits["test"])]
    ds_tr = GraphDataset([cases[i] for i in tr_idx], grid, cfg, library, None)
    norm = Normalizer.fit([{"x": g["x"], "edge_attr": g["edge_attr"]}
                           for g in ds_tr.graphs])
    ds_tr = GraphDataset([cases[i] for i in tr_idx], grid, cfg, library, norm)
    ds_va = GraphDataset([cases[i] for i in va_idx], grid, cfg, library, norm)
    ds_te = GraphDataset([cases[i] for i in te_idx], grid, cfg, library, norm)
    for d in (ds_tr, ds_va, ds_te):
        d.norm = norm
    return ds_tr, ds_va, ds_te, norm
