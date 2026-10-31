# -*- coding: utf-8 -*-
"""Polar-cut pattern comparison, LPR style: Simulation vs Diffraction / vs GNN."""

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
case = ds.cases[22]
batch = cast_batch(collate(ds.select([22])), ctx.dtype, ctx.device)
with torch.no_grad():
    sig_m3 = model(batch)["sig_db"][0].cpu().numpy()
tgt = ds.target_db[22].numpy()
pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
sig_m0 = BL.baseline_sigma_db(case.bits, ctx.grid.theta, ctx.grid.phi, library=ctx.library,
                              freq_ghz=cfg.physics.freq_ghz,
                              period_mm=cfg.physics.period_mm,
                              projection=cfg.physics.projection, pos_mm=pos)

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib import font_manager                          # noqa: E402
from PIL import Image, ImageChops                            # noqa: E402

have = {f.name for f in font_manager.fontManager.ttflist}
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
    if cand in have:
        plt.rcParams["font.sans-serif"] = [cand]
        break
plt.rcParams["axes.unicode_minus"] = False

NTH, NPH = 46, 180
T = tgt.reshape(NTH, NPH)
M0 = sig_m0.reshape(NTH, NPH)
M3 = sig_m3.reshape(NTH, NPH)
theta = ctx.grid.theta_ax

ang = np.concatenate([90.0 - theta, 90.0 + theta])
idx = np.argsort(ang)
ang = np.deg2rad(ang[idx])
cut = lambda A: np.concatenate([A[:, 0], A[:, 90]])[idx]
SIM, DIF, GNN = cut(T), cut(M0), cut(M3)

RMIN, RMAX = -25.0, 15.0
r = lambda v: np.clip(v, RMIN, RMAX) - RMIN
rho = lambda a, b: np.corrcoef(a, b)[0, 1]

fig = plt.figure(figsize=(9.8, 3.7))
panels = [
    ("(a) 仿真 vs 衍射模型", DIF, "#F2A03D", "Diffraction (M0)"),
    ("(b) 仿真 vs GNN", GNN, "#D9534F", "GNN (M3)"),
]
for k, (title, pred, color, label) in enumerate(panels):
    ax = fig.add_subplot(1, 2, k + 1, projection="polar")
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    ax.plot(ang, r(SIM), color="#2E6FD9", lw=1.9, label="Simulation")
    ax.plot(ang, r(pred), color=color, lw=1.9, label=label)

    ax.set_ylim(0, RMAX - RMIN)
    ax.set_yticks([0, 10, 20, 30, 40])
    ax.set_yticklabels([])
    ax.set_xticks(np.deg2rad([0, 30, 60, 90, 120, 150, 180]))
    ax.set_xticklabels(["0°", "30°", "60°", "90°", "120°", "150°", "180°"], fontsize=10.5)
    ax.grid(True, linestyle="--", alpha=0.55)
    ax.set_title(title, fontsize=12.5, pad=12)

    ax.text(0.02, 0.94, "ρ = %.3f" % rho(SIM, pred), transform=ax.transAxes,
            va="top", fontsize=12, color="#2B3845")

    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2,
              frameon=False, fontsize=11, handlelength=1.5, columnspacing=1.2)

# shared dB axis on the right, like the reference figure
cax = fig.add_axes([0.900, 0.30, 0.012, 0.42])
cax.set_ylim(RMIN, RMAX)
cax.set_xlim(0, 1)
cax.set_xticks([])
cax.set_yticks([-25, -15, -5, 5, 15])
cax.yaxis.tick_right()
cax.yaxis.set_label_position("right")
cax.set_ylabel("σ (dBsm)", fontsize=11, labelpad=6)
cax.tick_params(axis="y", labelsize=9, length=3, pad=3)
for sp in ("left", "top", "bottom"):
    cax.spines[sp].set_visible(False)
cax.spines["right"].set_color("#999999")

fig.subplots_adjust(left=0.02, right=0.87, top=0.88, bottom=0.16, wspace=0.20)

p = os.path.join(OUT, "polar_compare.png")
fig.savefig(p, dpi=240, facecolor="white")
plt.close(fig)

# trim the white margin around the drawing
im = Image.open(p).convert("RGB")
bg = Image.new("RGB", im.size, (255, 255, 255))
bbox = ImageChops.difference(im, bg).getbbox()
pad = 14
im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
         min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))).save(p, quality=95)

print("saved", p, Image.open(p).size)
print("rho(M0)=%.3f  rho(M3)=%.3f" % (rho(SIM, DIF), rho(SIM, GNN)))
print("theta=0: CST %.2f | M0 %.2f | M3 %.2f dBsm" % (T[0, 0], M0[0, 0], M3[0, 0]))





