# -*- coding: utf-8 -*-
"""Slide-ready figure: CST vs M0 vs M3 on one test sample (neutral titles)."""

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
OUT = r"D:/DSHNESS/GNN/fig_talk"
os.makedirs(OUT, exist_ok=True)

cfg = load_config(os.path.join(RUN, "config.yaml"))
ctx = build_context(cfg, out_dir=RUN, splits=load_splits(os.path.join(RUN, "splits.json")),
                    save=False, verbose=False)
model = build_model(ctx)
model.load_state_dict(torch.load(os.path.join(RUN, "best.pt"), map_location="cpu")["model"])
model.eval()

ds = ctx.ds["test"]
k = 0
case = ds.cases[k]
batch = cast_batch(collate(ds.select([k])), ctx.dtype, ctx.device)
with torch.no_grad():
    sig_m3 = model(batch)["sig_db"][0].cpu().numpy()
tgt = ds.target_db[k].numpy()
pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
sig_m0 = BL.baseline_sigma_db(case.bits, ctx.grid.theta, ctx.grid.phi, library=ctx.library,
                              freq_ghz=cfg.physics.freq_ghz,
                              period_mm=cfg.physics.period_mm,
                              projection=cfg.physics.projection, pos_mm=pos)

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib import font_manager                          # noqa: E402

have = {f.name for f in font_manager.fontManager.ttflist}
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
    if cand in have:
        plt.rcParams["font.sans-serif"] = [cand]
        break
plt.rcParams["axes.unicode_minus"] = False

T = ctx.grid.theta.reshape(46, 180)
PH = ctx.grid.phi.reshape(46, 180)

fig = plt.figure(figsize=(12, 3.0), constrained_layout=True)
panels = ((tgt, "(a) CST 全波仿真"), (sig_m0, "(b) M0：纯物理"), (sig_m3, "(c) M3：5 epoch"))
for i, (db, name) in enumerate(panels):
    ax = fig.add_subplot(1, 3, i + 1)
    im = ax.pcolormesh(PH, T, db.reshape(46, 180), shading="auto", cmap="turbo",
                       vmin=-25, vmax=15)
    ax.set_title(name, fontsize=13.5, pad=6)
    ax.set_xlabel("φ (deg)", fontsize=11)
    if i == 0:
        ax.set_ylabel("θ (deg)", fontsize=11)
    else:
        ax.set_yticklabels([])
    ax.tick_params(labelsize=9.5, length=3)
    if i == 2:
        cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.05)
        cb.set_label("σ (dBsm)", fontsize=10)
        cb.ax.tick_params(labelsize=9)


p = os.path.join(OUT, "patterns_compare.png")
fig.savefig(p, dpi=240, facecolor="white", bbox_inches="tight", pad_inches=0.03)
plt.close(fig)
print("saved", p)
print("case %d theta=0: CST %.2f | M0 %.2f | M3 %.2f dBsm"
      % (case.idx, tgt[0], sig_m0[0], sig_m3[0]))


