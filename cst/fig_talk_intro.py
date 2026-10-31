# -*- coding: utf-8 -*-
"""Intro figure: two unit cells (dimensions + reflection), 20x20 array, far-field pattern."""

import json
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

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib import font_manager                          # noqa: E402
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch  # noqa: E402

have = {f.name for f in font_manager.fontManager.ttflist}
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
    if cand in have:
        plt.rcParams["font.sans-serif"] = [cand]
        break
plt.rcParams["axes.unicode_minus"] = False

P, SUB_H = 14.0, 1.5
RADII = [(4.7, "单元 A（码 0）", "Γ = 0.867 ∠ −5.3°", "#C9A227"),
         (2.0, "单元 B（码 1）", "Γ = 0.852 ∠ 174.6°", "#C9A227")]

fig = plt.figure(figsize=(12.6, 4.0))
gs = fig.add_gridspec(1, 3, width_ratios=[6.0, 2.7, 3.9], wspace=0.12,
                      left=0.01, right=0.99, top=0.92, bottom=0.04)

# two unit-cell axes share the first grid cell, split horizontally
outer = gs[0, 0].subgridspec(1, 2, wspace=0.02)
for k, (r, name, gam, patch_col) in enumerate(RADII):
    ax = fig.add_subplot(outer[0, k])
    ax.set_xlim(0, 25.5)
    ax.set_ylim(-2.5, 27)
    ax.set_aspect("equal")
    ax.axis("off")

    # --- top view ---
    ax.add_patch(Rectangle((4, 12), P, P, fill=False, lw=1.6, ec="#444444"))
    ax.add_patch(Circle((4 + P / 2, 12 + P / 2), r, fc=patch_col, ec="#8A6D1F", lw=1.2, alpha=0.95))
    ax.annotate("", xy=(4 + P / 2 - r, 12 + P / 2), xytext=(4 + P / 2 + r, 12 + P / 2),
                arrowprops=dict(arrowstyle="<->", color="#B03A2E", lw=1.4))
    ax.text(4 + P / 2, 10.9, "2r = %.1f mm" % (2 * r), ha="center", va="top",
            fontsize=11, color="#B03A2E")
    ax.annotate("", xy=(2.6, 12), xytext=(2.6, 12 + P),
                arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.3))
    ax.text(1.9, 12 + P / 2, "P = 14", rotation=90, ha="right", va="center", fontsize=11, color="#555555")

    # --- side view ---
    ax.add_patch(Rectangle((4, 2), P, 0.6, fc="#3A3A3A", ec="none"))
    ax.add_patch(Rectangle((4, 2.6), P, SUB_H, fc="#BFD7EA", ec="#5B7C99", lw=1.2))
    ax.add_patch(Rectangle((4 + P / 2 - r, 2.6 + SUB_H), 2 * r, 0.45, fc=patch_col, ec="#8A6D1F", lw=1.2))
    ax.plot([19.5, 19.5], [2.6, 2.6 + SUB_H], color="#B03A2E", lw=1.3)
    ax.plot([19.5, 20.0], [2.6, 2.6], color="#B03A2E", lw=1.3)
    ax.plot([19.5, 20.0], [2.6 + SUB_H, 2.6 + SUB_H], color="#B03A2E", lw=1.3)
    ax.text(20.4, 2.6 + SUB_H / 2, "h = 1.5", ha="left", va="center", fontsize=10.5, color="#B03A2E")
    ax.text(11, 0.7, "εr = 2.65，tanδ = 0.0013，背面 PEC", ha="center", va="center", fontsize=10, color="#555555")

    ax.text(11, 26.6, name, ha="center", va="bottom", fontsize=13, color="#12263A", weight="bold")
    ax.text(11, -1.6, "r = %.1f mm　　%s" % (r, gam), ha="center", va="center", fontsize=11, color="#5E6B78")

# ---------------- array ----------------
ax_a = fig.add_subplot(gs[0, 1])
rec = json.load(open(r"D:\dataset\results\res_0000.json", encoding="utf-8"))
bits10 = np.array([int(c) for c in rec["code"]]).reshape(10, 10)
bits = np.repeat(np.repeat(bits10, 2, axis=0), 2, axis=1)
ax_a.imshow(bits, cmap="Blues", vmin=-0.35, vmax=1.25, interpolation="nearest",
            extent=[0, 20, 20, 0])
ax_a.set_xticks([0, 10, 20])
ax_a.set_yticks([0, 10, 20])
ax_a.tick_params(labelsize=9, length=2)
ax_a.set_xlabel("单元 (y)", fontsize=10)
ax_a.set_ylabel("单元 (x)", fontsize=10)
ax_a.set_title("20×20 阵列（400 单元，280 mm）", fontsize=12, pad=6)

# ---------------- far field ----------------
RUN = r"D:/DSHNESS/GNN/demo_out/run_m3_demo"
cfg = load_config(os.path.join(RUN, "config.yaml"))
ctx = build_context(cfg, out_dir=RUN, splits=load_splits(os.path.join(RUN, "splits.json")),
                    save=False, verbose=False)
ds = ctx.ds["test"]
case = ds.cases[22]
tgt = ds.target_db[22].numpy().reshape(46, 180)

TH = np.deg2rad(ctx.grid.theta_ax)[:, None]
PHI = np.deg2rad(np.arange(180) * 2.0)[None, :]
rlin = np.clip((tgt + 25.0) / 40.0, 0.0, 1.0)
X = rlin * np.sin(TH) * np.cos(PHI)
Y = rlin * np.sin(TH) * np.sin(PHI)
Z = rlin * np.cos(TH)

ax3 = fig.add_subplot(gs[0, 2], projection="3d")
norm = plt.Normalize(-25, 15)
ax3.plot_surface(X, Y, Z, facecolors=plt.cm.turbo(norm(tgt)), rstride=1, cstride=1,
                 linewidth=0, antialiased=False, shade=False)
ax3.set_box_aspect((1, 1, 0.55), zoom=1.18)
ax3.view_init(elev=28, azim=-60)
ax3.set_axis_off()
ax3.set_title("远场方向图（一个码，σ −25…15 dBsm）", fontsize=11.5, pad=-4)

fig.savefig(r"D:\DSHNESS\GNN\fig_talk\intro_design.png", dpi=240, facecolor="white",
            bbox_inches="tight", pad_inches=0.03)
print("saved")




