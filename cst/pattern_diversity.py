# -*- coding: utf-8 -*-
"""How diverse are the far-field patterns of the running random-code dataset?

Under a *pattern-modulation* objective (not RCS reduction), the question is not
how much the specular level moves, but how much the whole pattern moves.  This
script measures, for every finished case: peak level and direction, diffuse
level, and the pairwise correlation between patterns.
"""
import glob
import json
import os

import numpy as np

FF = r"D:\dataset\results\ff"
RES = r"D:\dataset\results"

files = sorted(glob.glob(os.path.join(FF, "ff_*.txt")))
rows = []
for f in files:
    i = int(os.path.basename(f)[3:7])
    rj = os.path.join(RES, "res_%04d.json" % i)
    if not os.path.isfile(rj):
        continue
    rec = json.load(open(rj, encoding="utf-8"))
    d = np.loadtxt(f)
    th, ph = d[:, 0], d[:, 1]
    p = 10 * np.log10(10 ** (d[:, 2] / 10) + 10 ** (d[:, 3] / 10))
    k = int(np.argmax(p))
    rows.append(dict(i=i, p=p, th=th, ph=ph, peak=p[k], pk_th=th[k], pk_ph=ph[k],
                     spec=rec["specular_dbsm"], ones=rec["code"].count("1")))

n = len(rows)
print("cases:", n)
print("peak level   : min %.2f  med %.2f  max %.2f dBsm"
      % (min(r["peak"] for r in rows), np.median([r["peak"] for r in rows]), max(r["peak"] for r in rows)))
print("peak theta   : min %.0f  med %.0f  max %.0f deg" % (
    min(r["pk_th"] for r in rows), np.median([r["pk_th"] for r in rows]), max(r["pk_th"] for r in rows)))
on_axis = sum(1 for r in rows if r["pk_th"] <= 6)
print("peak on axis (theta<=6 deg): %d / %d" % (on_axis, n))

th0 = rows[0]["th"]
mask = (th0 >= 6) & (th0 <= 60)
M = np.array([r["p"][mask] for r in rows])
C = np.corrcoef(M)
off = C[np.triu_indices(n, 1)]
print("\npairwise pattern correlation (theta 6..60, all phi):")
print("  min %.2f  p10 %.2f  median %.2f  p90 %.2f  max %.2f"
      % (off.min(), np.percentile(off, 10), np.median(off), np.percentile(off, 90), off.max()))

# how much of the field does the specular point represent
spec = np.array([r["spec"] for r in rows])
print("\nspecular: mean %.2f  std %.2f dB   (range %.2f..%.2f)"
      % (spec.mean(), spec.std(), spec.min(), spec.max()))
print("pattern mean level (theta 6..60): std across codes %.2f dB"
      % np.std([r["p"][mask].mean() for r in rows]))
