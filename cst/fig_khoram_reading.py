"""fig_khoram_reading.py —— 文献精读配图（4 联图）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 数据
N, R, PD, WS = 19, 3, 6, 7
err = [0.290, 0.288, 0.291, 0.289, 0.287]
gnn_t = [1.3, 4.1, 12.5, 25.1, 43.9]
tidy_t = [21, 42, 92, 307, 514]
cells = [100, 625, 2500, 5625, 10000]
labels = ["8λ\n100", "20λ\n625", "40λ\n2500", "60λ\n5625", "80λ\n10000"]

def bnd(i, j):
    if i < R or i >= N - R or j < R or j >= N - R:
        return 0
    if i < PD or i >= N - PD or j < PD or j >= N - PD:
        return 1
    return 2

fig = plt.figure(figsize=(15.5, 11.2))
gs = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.24,
                      left=0.06, right=0.965, top=0.915, bottom=0.07)

# ================================================== (a) 窗口几何与 stencil
ax = fig.add_subplot(gs[0, 0])
cmap = {0: "#e9ecef", 1: "#bcd9f2", 2: "#f6c667"}
for i in range(N):
    for j in range(N):
        ax.add_patch(Rectangle((j, N - 1 - i), 1, 1, facecolor=cmap[bnd(i, j)],
                               edgecolor="white", lw=0.35))
ax.add_patch(Circle((9.5, 9.5), 3.0, fill=False, ls="--", lw=2.0, ec="#c0392b"))
ax.plot([9.5], [9.5], marker="o", ms=7, color="#c0392b", zorder=5)
ax.annotate("R=3 圆邻域 → 29 个邻居(含自身)\n边权 1/r，自环 r=0.5",
            xy=(11.3, 10.6), xytext=(7.2, 14.0), fontsize=9,
            arrowprops=dict(arrowstyle="->", lw=1.2, color="#c0392b"), color="#c0392b")
ax.annotate("7×7 主窗\n(预测对象)", xy=(9.5, 6.4), xytext=(13.9, 3.2),
            fontsize=9, arrowprops=dict(arrowstyle="->", lw=1.0, color="#333"))
leg = [mpatches.Patch(fc=cmap[0], ec="gray", label="bnd=0  最外 R 格：邻域残缺→输出置零"),
       mpatches.Patch(fc=cmap[1], ec="gray", label="bnd=1  R~2R 缓冲"),
       mpatches.Patch(fc=cmap[2], ec="gray", label="bnd=2  主窗（送进解码器）")]
ax.legend(handles=leg, loc="lower left", bbox_to_anchor=(0.0, -0.02),
          fontsize=8.2, framealpha=0.95, borderpad=0.5)
ax.set_xlim(0, N); ax.set_ylim(0, N); ax.set_aspect("equal")
ax.set_xticks([0, 3, 6, 9.5, 13, 16, 19]); ax.set_yticks([0, 3, 6, 9.5, 13, 16, 19])
ax.tick_params(labelsize=8)
ax.set_title("(a) 训练样本的图几何：19×19=361 节点，仅 13×13 拥有完整 29 邻域",
             fontsize=11.5, loc="left", fontweight="bold")

# ================================================== (b) 感受野 vs 补边
ax = fig.add_subplot(gs[0, 1])
L = np.arange(1, 8)
depth = L * R
ax.fill_between([0.5, 7.5], 0, PD, color="#f6c667", alpha=.35, label="可用真实信息 halo=6 格")
ax.plot(L, depth, "o-", color="#c0392b", lw=2, ms=6, label="边界污染深度 = L·R")
ax.axhline(PD, color="#e67e22", ls="--", lw=1.6)
ax.text(7.35, PD + 0.6, "halo=2R=6", color="#e67e22", fontsize=9, ha="right")
ax.annotate("第 3 层起\n主窗已被\n人造边界污染", xy=(3, 9), xytext=(3.35, 2.2),
            fontsize=9.5, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2))
ax.set_xlabel("GNN 层数 L", fontsize=10)
ax.set_ylabel("距图上边界的作用深度（格）", fontsize=10)
ax.set_xticks(L); ax.set_xlim(0.5, 7.5); ax.set_ylim(0, 22)
ax.grid(alpha=.3, ls=":")
ax.legend(fontsize=8.5, loc="upper left")
ax.set_title("(b) 感受野(1+L·R=22 格≈17.6λ) 远大于补边(6 格) → 只能学“局部闭合”",
             fontsize=11.5, loc="left", fontweight="bold")

# ================================================== (c) 参数预算
ax = fig.add_subplot(gs[1, 0])
names = ["官方 GNN\n(29×1600×1600×5)", "官方输出层\n(29×1600×3456)",
         "复现 GNN\n(29×400×400×5)", "复现解码器\n(PixelShuffle)", "官方 CNN\n(4×5×5)"]
vals = [371.208, 160.362, 23.202, 0.779, 0.065]
cols = ["#2c3e50", "#5d6d7e", "#2980b9", "#27ae60", "#95a5a6"]
bars = ax.barh(range(len(vals))[::-1], vals, color=cols, height=.62)
for y, v in zip(range(len(vals))[::-1], vals):
    ax.text(v * 1.15, y, f"{v:.1f} M" if v > 1 else f"{v*1000:.0f} K",
            va="center", fontsize=9.5)
ax.set_yticks(range(len(vals))[::-1]); ax.set_yticklabels(names, fontsize=8.8)
ax.set_xscale("log"); ax.set_xlim(0.03, 3000)
ax.set_xlabel("参数量（M，对数轴）", fontsize=10)
ax.grid(axis="x", alpha=.3, ls=":")
ax.text(0.98, 0.06, "官方合计 ≈ 532 M\n复现合计 ≈ 24.8 M（↓21×）",
        transform=ax.transAxes, ha="right", fontsize=10,
        bbox=dict(fc="#fdf2e9", ec="#e67e22", lw=1))
ax.set_title("(c) “现代化”改动的真实代价：输出层 160M→0.74M，6 通道基样被抹掉",
             fontsize=11.5, loc="left", fontweight="bold")

# ================================================== (d) 误差与加速比
ax = fig.add_subplot(gs[1, 1])
x = np.arange(5)
ax.plot(x, err, "o-", color="#8e44ad", lw=2, ms=7)
for xi, e in zip(x, err):
    ax.annotate(f"{e:.3f}", (xi, e), textcoords="offset points", xytext=(0, 9),
                ha="center", fontsize=9, color="#8e44ad")
ax.set_ylim(0.27, 0.305); ax.set_ylabel("论文 Table 1 “error”\n(相对 L2，全程几乎不变)",
                                       fontsize=10, color="#8e44ad")
ax.tick_params(axis="y", labelcolor="#8e44ad")
ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
ax.grid(alpha=.3, ls=":")

ax2 = ax.twinx()
sp = [t / g for t, g in zip(tidy_t, gnn_t)]
ax2.bar(x, sp, width=.45, color="#2ecc71", alpha=.45, label="Tidy3D / GNN 加速比")
ax2.plot(x, sp, "s-", color="#27ae60", lw=1.6, ms=5)
for xi, s in zip(x, sp):
    ax2.annotate(f"{s:.1f}×", (xi, s), textcoords="offset points", xytext=(12, 2),
                 fontsize=8.8, color="#1e8449")
ax2.set_ylim(0, 20); ax2.set_ylabel("加速比（倍）", fontsize=10, color="#1e8449")
ax2.tick_params(axis="y", labelcolor="#1e8449")
ax.set_title("(d) 误差对尺寸近乎免疫(=0.29)，加速比却随尺寸下降(16→12×)",
             fontsize=11.5, loc="left", fontweight="bold")

fig.suptitle("Khoram et al., ACS Photonics 2023 精读：图几何 / 感受野 / 参数预算 / 标度行为",
             fontsize=14.5, fontweight="bold", y=0.972)
fig.savefig(r"D:\DSHNESS\GNN\fig_paper\fig_khoram_reading.png", dpi=200,
            bbox_inches="tight", facecolor="white")
print("saved")
