# -*- coding: utf-8 -*-
"""dB-domain correlation per case on the phi=0/180 cut, plus a few shape stats."""

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
order = np.argsort(np.concatenate([90.0 - theta, 90.0 + theta]))

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
    T, A0, A3 = tgt.reshape(46, 180), sig_m0.reshape(46, 180), sig_m3.reshape(46, 180)
    sim = np.concatenate([T[:, 0], T[:, 90]])[order]
    m0 = np.concatenate([A0[:, 0], A0[:, 90]])[order]
    m3 = np.concatenate([A3[:, 0], A3[:, 90]])[order]
    rd = lambda a, b: np.corrcoef(a, b)[0, 1]
    rows.append((k, case.idx, rd(sim, m0), rd(sim, m3),
                 float(np.max(sim)), float(np.max(m3))))

print("k idx | rho_db M0  M3 | peak_sim peak_M3")
for r in sorted(rows, key=lambda z: z[3]):
    print("%2d %3d | %.3f  %.3f | %6.2f %6.2f" % r)
