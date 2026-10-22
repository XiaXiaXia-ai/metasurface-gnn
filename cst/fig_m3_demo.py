# -*- coding: utf-8 -*-
"""训练后的 M3 与 CST / M0 在同一个 test 样本上的方向图对比（§10 的配图）。"""

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
OUT = r"D:/DSHNESS/GNN/demo_out"

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
fig = plt.figure(figsize=(13.5, 4.6))
for i, (db, name) in enumerate(((tgt, "(a) CST 全波仿真"),
                                (sig_m0, "(b) M0：镜面塌陷"),
                                (sig_m3, "(c) M3（5 epoch）：镜面补上"))):
    ax = fig.add_subplot(1, 3, i + 1)
    im = ax.pcolormesh(PH, T, db.reshape(46, 180), shading="auto", cmap="turbo",
                       vmin=-25, vmax=15)
    ax.set_title(name)
    ax.set_xlabel("φ (deg)")
    ax.set_ylabel("θ (deg)")
    if i == 2:
        fig.colorbar(im, ax=ax, label="σ (dBsm)")
fig.suptitle("test 样本 case %d：同一张方向图上的三种预测" % case.idx)
fig.tight_layout(rect=(0, 0, 1, 0.94))
p1 = os.path.join(OUT, "fig_m3_vs_m0.png")
fig.savefig(p1, dpi=140)
plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.6))
for j, ls in ((0, "-"), (45, "--")):
    ax.plot(ctx.grid.theta_ax, tgt.reshape(46, 180)[:, j], "k" + ls, lw=1.8,
            label="CST" if j == 0 else None)
    ax.plot(ctx.grid.theta_ax, sig_m0.reshape(46, 180)[:, j], "C1" + ls, lw=1.5,
            label="M0" if j == 0 else None)
    ax.plot(ctx.grid.theta_ax, sig_m3.reshape(46, 180)[:, j], "C0" + ls, lw=1.5,
            label="M3" if j == 0 else None)
ax.set_xlabel("θ (deg)")
ax.set_ylabel("σ (dBsm)")
ax.set_title("实线 = φ=0°（E 面），虚线 = φ=90°（H 面）")
ax.grid(alpha=0.3)
ax.legend()
fig.tight_layout()
p2 = os.path.join(OUT, "fig_m3_cuts.png")
fig.savefig(p2, dpi=140)
plt.close(fig)
print("saved:", p1)
print("saved:", p2)
print("case %d 镜面: CST %.3f | M0 %.3f | M3 %.3f dBsm"
      % (case.idx, tgt[0], sig_m0[0], sig_m3[0]))
