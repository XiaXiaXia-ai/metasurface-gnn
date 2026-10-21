# -*- coding: utf-8 -*-
"""Collect the run data, draw the comparison figure, and report the mesh size."""
import csv
import os
import random
import sys

import numpy as np

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIG = r"D:\DSHNESS\GNN\fig"
os.makedirs(FIG, exist_ok=True)

RUNS = [
    ("FR-4, r=3.65/5.6", r"D:\ff_bg15\post\summary.csv", "tab:gray"),
    ("er2.65, r=4.7/1.0", r"D:\ff_er265\post\summary.csv", "tab:blue"),
    ("er2.65, r=4.7/2.0", r"D:\ff_er265_r2\post\summary.csv", "tab:orange"),
    ("er2.65, r=4.7/2.0, 2x2  [baseline]", r"D:\ff_er265_r2_b2\post\summary.csv", "tab:red"),
]


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    f = np.array([float(r["case"].replace("ff_", "")) for r in rows])
    return (f, np.array([float(r["specular_db"]) for r in rows]),
            np.array([float(r["pec_plate_db"]) for r in rows]),
            np.array([float(r["reduction_db"]) for r in rows]))


data = [(lab, *load(path)) for lab, path, _ in RUNS]

fig, ax = plt.subplots(1, 2, figsize=(12, 4.4), facecolor="white")
for i, (lab, f, spec, plate, red) in enumerate(data):
    c = RUNS[i][2]
    ax[0].plot(f, red, "o-", color=c, label=lab, lw=1.6, ms=4)
    ax[1].plot(f, spec, "o-", color=c, label=lab, lw=1.6, ms=4)

ax[1].plot(data[0][1], data[0][2], "k--", lw=1.2, label="PEC plate reference")
ax[0].set_xlabel("Frequency (GHz)")
ax[0].set_ylabel("RCS reduction vs PEC plate (dB)")
ax[0].set_title("Specular RCS reduction")
ax[0].grid(alpha=0.3)
ax[0].legend(fontsize=7.5)

ax[1].set_xlabel("Frequency (GHz)")
ax[1].set_ylabel("Specular RCS (dBsm)")
ax[1].set_title("Absolute specular level")
ax[1].grid(alpha=0.3)
ax[1].legend(fontsize=7.5)

fig.tight_layout()
out = os.path.join(FIG, "comparison.png")
fig.savefig(out, dpi=170)
print("figure:", out)

# ---- block code statistics (same generation as build_coding_array.py) ----
N, BLOCK, SEED = 20, 2, 20261020
NB = N // BLOCK
rng = random.Random(SEED)
bits = [[rng.randint(0, 1) for _ in range(NB)] for _ in range(NB)]
ones = sum(sum(row) for row in bits)
print("block code: %d x %d macro cells, %d ones / %d zeros"
      % (NB, NB, ones, NB * NB - ones))
for row in bits:
    print("".join(str(b) for b in row))

# ---- mesh size of the delivered model ----
import cst.interface  # noqa: E402

de = cst.interface.DesignEnvironment.connect_to_any()
prj = [p for p in de.get_open_projects()
       if p.filename().lower().endswith("er265_r2_b2.cst")]
if prj:
    m = prj[0].model3d
    m.add_to_history("create mesh", "Mesh.Update", timeout=1800)
    print("mesh cells: %d  (Nx=%d Ny=%d Nz=%d)"
          % (m.Mesh.GetNumberOfMeshCells(), m.Mesh.GetNx(), m.Mesh.GetNy(), m.Mesh.GetNz()))
else:
    print("mesh cells: project not open")
