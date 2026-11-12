# -*- coding: utf-8 -*-
"""Schematic of the proposed ESS ON unit cell (no CST, geometry only)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

P = 15.0
wr, wb, wp, hp = 2.4, 2.4, 7.8, 6.0
g = 1.0
a = P/2 - wr
yb = a - g
H0 = P/2

fig, ax = plt.subplots(figsize=(7.8, 7.8))
ax.set_aspect("equal")
ax.set_xlim(-9.2, 9.2)
ax.set_ylim(-9.2, 9.2)

ax.add_patch(Rectangle((-H0, -H0), P, P, fill=False, ls=(0, (5, 4)), lw=1.4, ec="0.35"))
ring = [
    (-H0, -H0, P, wr),
    (-H0, a, P, wr),
    (-H0, -a, wr, 2*a),
    (a, -a, wr, 2*a),
]
for x, y, w, h in ring:
    ax.add_patch(Rectangle((x, y), w, h, fc="#cdd0d5", ec="#3b3f46", lw=1.0, zorder=2))
ax.add_patch(Rectangle((-wb/2, -yb), wb, 2*yb, fc="#bcc0c7", ec="#3b3f46", lw=1.0, zorder=3))
ax.add_patch(Rectangle((-wp/2, -hp/2), wp, hp, fc="#b1b6bf", ec="#3b3f46", lw=1.0, zorder=4))
for s in (1, -1):
    y1, y2 = s*yb, s*a
    ax.plot([0, 0], [y1, y2], color="#d62728", lw=8, solid_capstyle="butt", zorder=6)
    ax.plot([0], [(y1+y2)/2], marker="o", ms=4.2, color="white", mec="#d62728", mew=1.2, zorder=7)

def arrow(x0, y0, x1, y1, text, tx, ty, ha="center", va="center", color="#1f5fa8"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="<->", mutation_scale=9,
                                 lw=1.05, color=color, shrinkA=0, shrinkB=0, zorder=8))
    ax.text(tx, ty, text, color=color, fontsize=9.5, ha=ha, va=va, zorder=9,
            bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.2))

def ext(x0, y0, x1, y1):
    ax.plot([x0, x1], [y0, y1], color="#1f5fa8", lw=0.6, ls=(0, (2, 2)), zorder=1)

# wr: outside the right edge
ext(H0, a, 8.35, a); ext(H0, H0, 8.35, H0)
arrow(8.15, a, 8.15, H0, "wr", 8.45, (a+H0)/2, ha="left")
# wb: above pad, straddling bar
arrow(-wb/2, 3.62, wb/2, 3.62, "wb", 1.55, 3.72, ha="left")
# wp: across pad
arrow(-wp/2, -1.9, wp/2, -1.9, "wp", 2.55, -1.72, ha="left")
# hp: in right slot between pad and ring
ext(wp/2, -hp/2, 4.62, -hp/2); ext(wp/2, hp/2, 4.62, hp/2)
arrow(4.48, -hp/2, 4.48, hp/2, "hp", 4.63, 0.0, ha="left")
# g: vertical gap
arrow(1.15, yb, 1.15, a, "g=1.0", 1.28, (yb+a)/2, ha="left")

ax.text(-7.3, 7.05, "PEC ring, outer 15 x 15", fontsize=9.2, color="#333333", zorder=10)
ax.text(-7.3, 6.25, "central bar + merged pad", fontsize=9.2, color="#333333", zorder=10)
ax.text(0, 8.55, "Proposed ESS ON cell: P=15 mm, h=3 mm vacuum, ground z=-3 mm, metal z=0",
        ha="center", va="bottom", fontsize=9.5)
ax.text(0, -8.35, "only two lumped-element bridges (red) connect bar to ring; PEC ring touches periodic boundary",
        ha="center", va="top", fontsize=8.6, color="#8b1a1a")
ax.set_xlabel("x (mm)")
ax.set_ylabel("y (mm)")
ax.grid(True, lw=0.3, color="0.87")
ax.set_xticks(range(-7, 8, 1))
ax.set_yticks(range(-7, 8, 1))
ax.tick_params(labelsize=8)

fig.tight_layout()
fig.savefig(r"D:\DSHNESS\GNN\_sub_unit_cell.png", dpi=220)
print("saved _sub_unit_cell.png")
