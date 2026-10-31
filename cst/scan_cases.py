# -*- coding: utf-8 -*-
"""Scan test cases: single-cut correlation for M0 and M3, to pick a representative sample."""

import os
import sys

import numpy as np

sys.path.insert(0, r"D:/GNN/gnn")

import torch  # noqa: E402

import msgnn.physics.baseline as BL                       # noqa: E402
from msgnn.config import load_config                       # noqa: E402
from msgnn.data.build_graph import collate                 # noqa: E402
from msgnn.data.dataset import load_splits                 # noqa: E402
from msgnn.experiment import build_context, build_model, cast_batch  # noqa: E402
from msgnn.physics import radiation as R                   # noqa: E402

RUN = r"D:/DSHNESS/GNN/demo_out/run_m3_demo"
cfg = load_config(os.path.join(RUN, "config.yaml"))
ctx = build_context(cfg, out_dir=RUN, splits=load_splits(os.path.join(RUN, "splits.json")),
                    save=False, verbose=False)
model = build_model(ctx)
model.load_state_dict(torch.load(os.path.join(RUN, "best.pt"), map_location="cpu")["model"])
model.eval()

pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
theta = ctx.grid.theta_ax
ang = np.concatenate([90.0 - theta, 90.0 + theta])
idx = np.argsort(ang)

ds = ctx.ds["test"]
rows = []
for k in range(len(ds.cases)):
    case = ds.cases[k]
    batch = cast_batch(collate(ds.select([k])), ctx.dtype, ctx.device)
    with torch.no_grad():
        sig_m3 = model(batch)["sig_db"][0].cpu().numpy()
    tgt = ds.target_db[k].numpy()
    sig_m0 = BL.baseline_sigma_db(case.bits, ctx.grid.theta, ctx.grid.phi, library=ctx.library,
                                  freq_ghz=cfg.physics.freq_ghz,
                                  period_mm=cfg.physics.period_mm,
                                  projection=cfg.physics.projection, pos_mm=pos)

    cut = lambda A: np.concatenate([A.reshape(46, 180)[:, 0],
                                    A.reshape(46, 180)[:, 90]])[idx]
    sim, m0, m3 = cut(tgt), cut(sig_m0), cut(sig_m3)
    p = lambda a: 10 ** (a / 10)
    rho = lambda a, b: np.corrcoef(p(a), p(b))[0, 1]
    rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))

    rows.append((k, case.idx, rho(sim, m0), rho(sim, m3),
                 abs(tgt[0] - sig_m0[0]), abs(tgt[0] - sig_m3[0]),
                 rmse(tgt, sig_m0), rmse(tgt, sig_m3)))

print("cut-scan: per case, worst cut (linear) and dB corr on phi=0 cut")


