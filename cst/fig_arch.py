"""fig_arch.py —— Khoram 2023 架构与单层内部示意（两联图）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

fig = plt.figure(figsize=(16, 8.6))
gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.10,
                      left=0.025, right=0.985, top=0.885, bottom=0.03)

C_BLUE, C_ORANGE, C_GREEN, C_GREY = "#dbe9f7", "#fde8c8", "#d8f0dd", "#eceff1"


def box(ax, x, y, w, h, title, sub, fc, ts=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.015",
                                fc=fc, ec="#5d6d7e", lw=1.2))
    ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center",
            fontsize=ts, fontweight="bold", color="#1b2631")
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
            fontsize=8.4, color="#34495e", linespacing=1.45)


def arrow(ax, x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=14,
                                 lw=1.5, color="#566573"))


# ============================================================ (a) 数据流
ax = fig.add_subplot(gs[0])
ax.set_xlim(0, 100); ax.set_ylim(0, 30); ax.axis("off")
ax.text(0.5, 28.6, "(a) 一次前向的形状与参数量（数值由 khoram_minimal.py 实测）",
        fontsize=12, fontweight="bold")

y0, h, w = 9.5, 15.0, 14.0
xs = [1.5, 17.6, 33.7, 49.8, 65.9, 82.0]

box(ax, xs[0], y0, w, h, "① 输入图",
    "19×19 节点 × 5 特征\n361 × 5\nR, H, Dx, Dy, bnd", C_GREY)
box(ax, xs[1], y0, w, h, "② 7 × GCL",
    "Eq.(1) 消息传递\n隐层 1600 / 输出 3456\n全图共用一套权重", C_BLUE)
box(ax, xs[2], y0, w, h, "③ mask 取主窗",
    "361 → 49 个节点\n49 × 3456\n丢掉补边的 312 个", C_GREY)
box(ax, xs[3], y0, w, h, "④ stitch 拼图",
    "每节点 = 6×24×24 场块\n拼成 6×168×168\n即“6 通道基样”", C_ORANGE)
box(ax, xs[4], y0, w, h, "⑤ 4 × conv5×5",
    "6→24→48→24→6\nReLU×3，末层线性\n感受野 17 px ≈ 0.7 单元", C_GREEN)
box(ax, xs[5], y0, w, h, "⑥ 近场输出",
    "6 × 168 × 168\nEx,Ey,Ez 的实/虚部\nλ/2 平面上方", C_GREY)

for i in range(5):
    arrow(ax, xs[i] + w, y0 + h / 2, xs[i + 1] - 0.15, y0 + h / 2)

ax.text(xs[1] + w / 2, y0 + h + 1.6, "531.80 M 参数", ha="center",
        fontsize=9.5, color="#c0392b", fontweight="bold")
ax.text(xs[4] + w / 2, y0 + h + 1.6, "64.9 K 参数", ha="center",
        fontsize=9.5, color="#1e8449", fontweight="bold")
ax.text(xs[3] + w / 2, y0 - 1.7, "0 参数（纯 reshape）", ha="center",
        fontsize=8.6, color="#7f8c8d")
ax.text(xs[2] + w / 2, y0 - 1.7, "0 参数", ha="center", fontsize=8.6, color="#7f8c8d")

ax.text(50, 2.6, "整个 GNN 只有一套权重：靠“29 邻域 + 深度”把 5 维几何映射到 3456 维场块。"
                 "尺寸泛化来自“权重与节点数无关”，不是来自图结构。",
        ha="center", va="center", fontsize=9.6, color="#2c3e50",
        bbox=dict(fc="#fdf2e9", ec="#e67e22", lw=1.0, pad=5))

# ============================================================ (b) 单层内部
ax = fig.add_subplot(gs[1])
ax.set_xlim(0, 100); ax.set_ylim(0, 26); ax.axis("off")
ax.text(0.5, 24.8, "(b) 一层 GCL 内部：论文 Eq.(1) 的三种等价写法",
        fontsize=12, fontweight="bold")

# 左：圆邻域示意
cx, cy = 9.5, 14.6
for i in range(-3, 4):
    for j in range(-3, 4):
        if i * i + j * j <= 9:
            ax.add_patch(Circle((cx + j * 2.05, cy + i * 2.05), 0.45,
                                fc="#c0392b" if (i, j) == (0, 0) else "#5dade2", ec="none"))
        else:
            ax.add_patch(Circle((cx + j * 2.05, cy + i * 2.05), 0.22, fc="#d5dbdb", ec="none"))
ax.add_patch(Circle((cx, cy), 3.15, fill=False, ls="--", lw=1.2, ec="#c0392b"))
ax.text(cx, cy - 8.6, "R=3 → 29 邻居（含自身）", ha="center", fontsize=8.6, color="#34495e")

y0b, hb = 9.4, 10.0
bw = 16.0
bxs = [21.0, 39.5, 58.0, 76.5]

box(ax, bxs[0], y0b, bw, hb, "取 29 个邻居",
    "z_u ∈ R^1600，共 29 个\n逐个 ÷ r_uv", C_BLUE, 9.6)
box(ax, bxs[1], y0b, bw, hb, "concat",
    "29 × 1600 = 46400\n顺序由 (k,l) 遍历固定", C_BLUE, 9.6)
box(ax, bxs[2], y0b, bw, hb, "× W  (46400→1600)",
    "74.2 M 权重 / 层\n块对角 ≡ 29 个独立矩阵", "#f5b7b1", 9.6)
box(ax, bxs[3], y0b, bw, hb, "+ b → LeakyReLU",
    "邻域不完整 → 整行置 0\n输出 z_v^{l+1} ∈ R^1600", C_GREEN, 9.6)

for i in range(3):
    arrow(ax, bxs[i] + bw, y0b + hb / 2, bxs[i + 1] - 0.15, y0b + hb / 2)
ax.add_patch(FancyArrowPatch((cx + 7.3, cy), (bxs[0] - 0.2, y0b + hb / 2),
                             arrowstyle="-|>", mutation_scale=14, lw=1.5, color="#566573"))

ax.text(50, 2.6,
        "A（论文 Eq.1）：  Σ_u W_u z_u / r_uv"
        "        B（官方代码）：  concat 后乘一个大矩阵（块对角，与 A 完全相同）"
        "        C（等价形式）：  7×7 圆形掩膜卷积，每 tap 一个 1600×1600 矩阵\n"
        "已数值验证：max|A−C| = 5.4e-7（float32）；1/r 可被 W_u 精确吸收（2.4e-7），故“距离加权”不构成表达力约束。",
        ha="center", va="center", fontsize=9.2, color="#1b2631", linespacing=1.8,
        bbox=dict(fc="#eef7fb", ec="#2980b9", lw=1.0, pad=6))

fig.suptitle("Khoram et al., ACS Photonics 2023：模型架构与单层内部",
             fontsize=14.5, fontweight="bold", y=0.955)
fig.savefig(r"D:\DSHNESS\GNN\fig_paper\fig_arch.png", dpi=190,
            bbox_inches="tight", facecolor="white")
print("saved")
