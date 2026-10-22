# -*- coding: utf-8 -*-
"""Experiment context: snapshot -> cases -> splits -> datasets -> operator -> model.

Every entry point (train / evaluate / predict / smoke test) goes through
build_context() so that the frozen file list, the split and the normalisation
statistics are byte-identical between training and evaluation.

Order of operations (this is the data-leakage guard):
  1. freeze the file list (snapshot.json) -- new CST cases appearing later are
     ignored for the lifetime of the run;
  2. build the layout-grouped split (splits.json);
  3. fit the normaliser on the TRAIN graphs only;
  4. build the operator (parameter free, identical for all splits).
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import torch

from .config import Config
from .data.build_graph import GraphDataset, make_datasets
from .data.dataset import (Grid, build_snapshot, load_or_make_splits,
                          load_snapshot, load_splits, save_snapshot, save_splits,
                          scan_cases)
from .data.normalizer import Normalizer
from .models.pipeline import build_pipeline
from .physics import radiation as R
from .physics.unit_library import UnitLibrary


@dataclass
class Context:
    cfg: Config
    out_dir: str
    grid: Grid
    cases: list
    splits: dict
    ds: Dict[str, GraphDataset]
    norm: Optional[Normalizer]
    operator: object
    library: UnitLibrary
    dtype: torch.dtype
    device: str
    snapshot_path: Optional[str] = None

    @property
    def n_nodes(self) -> int:
        return self.cfg.physics.n_side ** 2

    @property
    def node_dim(self) -> int:
        return int(self.ds["train"].graphs[0]["x"].shape[1])

    @property
    def edge_dim(self) -> int:
        return int(self.ds["train"].graphs[0]["edge_attr"].shape[1])


def dtype_of(cfg: Config) -> torch.dtype:
    return torch.float64 if cfg.runtime.dtype == "float64" else torch.float32


def set_threads(cfg: Config) -> None:
    try:
        torch.set_num_threads(int(cfg.runtime.threads))
    except Exception:                                    # noqa: BLE001
        pass


def cast_batch(batch: dict, dtype: torch.dtype, device: str = "cpu") -> dict:
    out = {}
    for k, v in batch.items():
        if isinstance(v, torch.Tensor) and v.is_floating_point():
            out[k] = v.to(dtype=dtype, device=device)
        elif isinstance(v, torch.Tensor):
            out[k] = v.to(device=device)
        else:
            out[k] = v
    return out


def build_context(cfg: Config, out_dir: Optional[str] = None,
                  snapshot_path: Optional[str] = None, max_train: int = 0,
                  norm: Optional[Normalizer] = None, splits: Optional[dict] = None,
                  save: bool = True, verbose: bool = True,
                  max_cases: int = 0) -> Context:
    out_dir = out_dir or cfg.out_dir
    if save:
        os.makedirs(out_dir, exist_ok=True)
    set_threads(cfg)

    # ---- 1. snapshot (frozen file list)
    snap = None
    cand = snapshot_path
    if cand is None and os.path.isfile(os.path.join(out_dir, "snapshot.json")):
        cand = os.path.join(out_dir, "snapshot.json")
    if cand is None:
        cand = cfg.data.snapshot
    if cand and os.path.isfile(cand):
        snap = load_snapshot(cand)
        snapshot_path = cand
    elif save:
        snap = build_snapshot(cfg.data, Grid.from_step(2.0), hash_files=True,
                              block=cfg.physics.block, n_side=cfg.physics.n_side)
        snapshot_path = save_snapshot(snap, os.path.join(out_dir, "snapshot.json"))
    if snap is None:
        raise RuntimeError("no snapshot available and save=False")

    grid = Grid.from_step(float(snap.get("grid", {}).get("step", 2.0)))
    if int(snap["n"]) == 0:
        raise RuntimeError("snapshot contains no cases")

    # ---- 2. cases + split
    cases, warns = scan_cases(cfg.data, grid, snap, verbose=verbose,
                              block=cfg.physics.block, n_side=cfg.physics.n_side)
    if not cases:
        raise RuntimeError("no usable cases found under %s" % cfg.data.root)
    if splits is None and os.path.isfile(os.path.join(out_dir, "splits.json")):
        splits = load_splits(os.path.join(out_dir, "splits.json"))
    if splits is None:
        splits = load_or_make_splits(cfg.data, cases)
    if max_cases and len(cases) > int(max_cases):
        # keep the split assignment of the full set but evaluate a subset of it
        k = int(max_cases)
        n_tr = max(1, int(round(0.7 * k)))
        n_va = max(1, int(round(0.15 * k)))
        n_te = max(1, k - n_tr - n_va)
        keep = (set(splits["train"][:n_tr]) | set(splits["val"][:n_va])
                | set(splits["test"][:n_te]))
        cases = [c for c in cases if c.idx in keep]
    if save:
        save_splits(splits, os.path.join(out_dir, "splits.json"))

    # ---- 3./4. datasets + operator
    library = UnitLibrary.floquet(cfg.physics.freq_ghz, cfg.physics.gamma_source)
    ds_tr, ds_va, ds_te, fitted = make_datasets(cfg, cases, grid, splits,
                                                library=library, max_train=max_train)
    if norm is not None:
        ds_tr = GraphDataset(ds_tr.cases, grid, cfg, library, norm)
        ds_va = GraphDataset(ds_va.cases, grid, cfg, library, norm)
        ds_te = GraphDataset(ds_te.cases, grid, cfg, library, norm)
        for d in (ds_tr, ds_va, ds_te):
            d.norm = norm
        fitted = norm
    pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
    op = R.FarFieldOperator(grid.theta, grid.phi, pos_mm=pos,
                            freq_ghz=cfg.physics.freq_ghz,
                            period_mm=cfg.physics.period_mm,
                            projection=cfg.physics.projection,
                            dtype=dtype_of(cfg),
                            chunk_m=0 if grid.size <= 20000 else 8192)
    if verbose:
        print("[ctx] cases=%d  train=%d val=%d test=%d  nodes=%d  angles=%d"
              % (len(cases), len(ds_tr), len(ds_va), len(ds_te),
                 cfg.physics.n_side ** 2, grid.size))
    return Context(cfg=cfg, out_dir=out_dir, grid=grid, cases=cases, splits=splits,
                   ds={"train": ds_tr, "val": ds_va, "test": ds_te}, norm=fitted,
                   operator=op, library=library, dtype=dtype_of(cfg),
                   device=cfg.runtime.device, snapshot_path=snapshot_path)


def build_model(ctx: Context):
    model = build_pipeline(ctx.cfg, ctx.node_dim, ctx.edge_dim,
                           ctx.grid.n_theta, ctx.grid.n_phi, ctx.operator)
    return model.to(dtype=ctx.dtype)
