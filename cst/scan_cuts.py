# -*- coding: utf-8 -*-
"""For each test case and several cuts, compute rho (linear and dB) for M0 / M3."""

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
base = np.concatenate([90.0 - theta, 90.0 + theta])
order = np.argsort(base)

ds = ctx.ds["test"]
CUTS = [0, 45, 90, 135]
best = []
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
    T, A0, A3 = tgt.reshape(46, 180), sig_m0.reshape(46, 180), sig_m3.reshape(46, 180)

    for c in CUTS:
        j = c // 2
        j2 = (c + 180) % 360 // 2
        sim = np.concatenate([T[:, j], T[:, j2]])[order]
        m0 = np.concatenate([A0[:, j], A0[:, j2]])[order]
        m3 = np.concatenate([A3[:, j], A3[:, j2]])[order]
        p = lambda a: 10 ** (a / 10)
        rl = lambda a, b: np.corrcoef(p(a), p(b))[0, 1]
        rd = lambda a, b: np.corrcoef(a, b)[0, 1]
        best.append((k, case.idx, c, rl(sim, m0), rl(sim, m3), rd(sim, m3)))

print("case idx cut | rho_lin M0  rho_lin M3  rho_db M3")
for r in sorted(best, key=lambda z: z[4])[:18]:
    print("%3d %4d %3d | %.3f  %.3f  %.3f" % r)
print("---- highest rho_db(M3) spread ----")
for r in sorted(best, key=lambda z: z[5])[:8]:
    print("%3d %4d %3d | %.3f  %.3f  %.3f" % r)
