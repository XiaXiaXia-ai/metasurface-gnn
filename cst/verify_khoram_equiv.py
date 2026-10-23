"""
verify_khoram_equiv.py
======================
对 Khoram et al., ACS Photonics 2023 (DOI 10.1021/acsphotonics.2c01019) 的
消息传递层做三项数值核验（只用 torch，不需要 PyG / DGL）：

  V1  邻域规模：R=1,2,3,4 的圆邻域点数；19x19 图中有多少节点具备完整 29 邻域
  V2  等价性：Eq.(1) 的 "邻居定序拼接 + 单一大矩阵" 实现
              == 一个 7x7 圆形掩膜的 conv2d（每个偏移一个独立 Cin->Cout 矩阵）
  V3  吸收性：对 tanh 之前的线性算子而言，1/r 距离权重可被逐偏移权重矩阵完全吸收
              （输出集合不变），即它不是表达力约束，只是初始化尺度/正则
  V4  置换敏感性：打乱拼接顺序 => 输出改变（证明该层不是置换不变的）

运行：python verify_khoram_equiv.py
"""
import itertools
import numpy as np
import torch
import torch.nn.functional as F

torch.manual_seed(0)
np.random.seed(0)


def circle_offsets(R):
    """按论文/官方代码的遍历顺序 (k 外层, l 内层) 返回圆邻域偏移, 含自身。"""
    offs = []
    for k in range(-R, R + 1):
        for l in range(-R, R + 1):
            if k * k + l * l <= R * R:
                offs.append((k, l))
    return offs


def build_graph(N, R):
    """返回 edge_index[2,E], 每个目标节点的邻居偏移顺序, 以及每节点入度。"""
    idx = {(i, j): i * N + j for i in range(N) for j in range(N)}
    offs = circle_offsets(R)
    src, dst = [], []
    for i in range(N):
        for j in range(N):
            for k, l in offs:
                ni, nj = i + k, j + l
                if 0 <= ni < N and 0 <= nj < N:
                    src.append(idx[(ni, nj)])
                    dst.append(idx[(i, j)])
    deg = np.bincount(np.array(dst), minlength=N * N)
    return torch.tensor([src, dst]), offs, deg


def msgpass_concat(z, W, r, offs, N):
    """Eq.(1) 的忠实实现：按固定偏移顺序拼接邻居(已除 r)，再乘单一 (29*Cin, Cout) 矩阵。"""
    Cin = z.shape[1]
    Cout = W.shape[1]
    zf = z[0].permute(1, 2, 0)  # (1,Cin,N,N) -> (N,N,Cin)
    out = torch.zeros(N * N, Cout, dtype=z.dtype)
    for i in range(N):
        for j in range(N):
            if min(i, j, N - 1 - i, N - 1 - j) < max(abs(k) for k, _ in offs):
                continue  # 邻域不完整 -> 论文/代码里输出直接置零
            chunks = []
            for (k, l) in offs:
                chunks.append(zf[i + k, j + l] / r[(k, l)])
            out[i * N + j] = torch.cat(chunks) @ W
    return out.reshape(N, N, Cout).permute(2, 0, 1).unsqueeze(0)


def conv_equiv(z, K, Cin, Cout, R):
    """用 conv2d + 圆形掩膜核复现同一算子（核内每个偏移一个独立 Cin->Cout 矩阵）。"""
    w = torch.zeros(Cout, Cin, 2 * R + 1, 2 * R + 1)
    for (k, l), mat in K.items():
        w[:, :, R + k, R + l] = mat.T  # (Cin,Cout) -> (Cout,Cin)
    return F.conv2d(z, w)


def main():
    print("=" * 72)
    print("V1  邻域规模")
    print("=" * 72)
    for R in (1, 2, 3, 4):
        offs = circle_offsets(R)
        N = 7 + 4 * R  # 保证内部有完整邻域
        _, _, deg = build_graph(N, R)
        full = int((deg == len(offs)).sum())
        print(f"  R={R}: 圆邻域点数={len(offs):3d}   图 {N}x{N}={N*N} 节点中"
              f"具备完整邻域者={full} (={int(np.sqrt(full))}x{int(np.sqrt(full))})")

    # ---- 主检验用 R=3, 19x19（与论文/代码完全一致的窗口几何）----
    R, N = 3, 19
    offs = circle_offsets(R)
    _, _, deg = build_graph(N, R)
    full_mask = torch.tensor(deg == len(offs)).reshape(N, N)
    inner = int(full_mask.sum())
    print(f"\n  论文窗口: 7x7 主窗 + 2R=6 padding -> {N}x{N}={N*N} 节点, "
          f"完整邻域节点 {inner} ({int(np.sqrt(inner))}x{int(np.sqrt(inner))}, "
          f"位于 [3,15]^2)")

    Cin, Cout = 3, 2
    z = torch.randn(1, Cin, N, N)
    W = torch.randn(len(offs) * Cin, Cout) * 0.1

    # 距离：格点距离，自环 r=0.5（论文 r_vv=0.5，官方代码 dist==0 -> 0.5）
    r = {}
    for (k, l) in offs:
        d = (k * k + l * l) ** 0.5
        r[(k, l)] = 0.5 if d == 0 else d

    out_msg = msgpass_concat(z, W, r, offs, N)

    # ---- V2 等价性 ----
    print("\n" + "=" * 72)
    print("V2  Eq.(1) 拼接实现  vs  7x7 圆形掩膜 conv2d")
    print("=" * 72)
    K = {}
    for t, (k, l) in enumerate(offs):
        K[(k, l)] = (W[t * Cin:(t + 1) * Cin] / r[(k, l)]).reshape(Cin, Cout)
    out_conv = conv_equiv(z, K, Cin, Cout, R)

    # conv 的有效区是 (N-2R)x(N-2R)，对应 [R, N-1-R]^2 == [3,15]^2
    core = out_msg[:, :, R:N - R, R:N - R]
    err = (core - out_conv).abs().max().item()
    print(f"  max|msgpass - conv2d| = {err:.3e}   (dtype float32, 量级 {core.abs().max():.2f})")
    print("  结论: 数值上恒等。该 GNN 层 == 核大小为 7x7、仅保留圆内 29 个 tap、"
          "\n        每个 tap 一个独立 (Cin->Cout) 矩阵的卷积层。")

    # ---- V3 1/r 吸收 ----
    print("\n" + "=" * 72)
    print("V3  1/r 是否构成表达力约束")
    print("=" * 72)
    r1 = {o: 1.0 for o in offs}
    W_absorbed = torch.stack([
        W[t * Cin:(t + 1) * Cin] / r[o] for t, o in enumerate(offs)
    ]).reshape(-1, Cout)
    out_absorbed = msgpass_concat(z, W_absorbed, r1, offs, N)
    err2 = (out_msg - out_absorbed).abs().max().item()
    print(f"  用 W'_o = W_o/r_o 且令 r≡1 重算: max|Δ| = {err2:.3e}")
    print("  结论: 给定逐偏移独立权重, 任何 1/r 权重都能被权重矩阵精确吸收 =>"
          "\n        它不改变可达函数集合, 只改变初始化尺度。它与非线性配合也不改变"
          "\n        表达力（因为除法发生在逐偏移线性映射之前，等价于缩放该偏移的矩阵）。")

    # ---- V4 置换敏感性 ----
    print("\n" + "=" * 72)
    print("V4  拼接顺序 == 置换不变性？")
    print("=" * 72)
    perm = torch.randperm(len(offs))
    offs_p = [offs[i] for i in perm]
    # 权重矩阵不变，只改变"邻居被拼接的顺序"（等价于另一个图库的边枚举顺序）
    out_perm = msgpass_concat(z, W, r, offs_p, N)
    d = (core - out_perm[:, :, R:N - R, R:N - R]).abs()
    print(f"  同一套权重、仅改变邻居枚举顺序: 平均偏差={d.mean().item():.3f}, "
          f"最大={d.max().item():.3f} (输出量级 {core.abs().mean():.3f})")
    print("  结论: 层输出依赖邻居的枚举顺序 => 不是集合算子，是结构化模板（stencil）。"
          "\n        只有在规则方格上 '第 k 个邻居' 才有定义。")

    # ---- V5 感受野 / 补边 ----
    print("\n" + "=" * 72)
    print("V5  感受野 vs 补边宽度")
    print("=" * 72)
    L, Rr, halo = 7, 3, 6
    print(f"  论文配置: L={L} 层, R={Rr}, 补边 halo={halo} 格 (=2R)")
    for l in range(1, L + 1):
        depth = Rr * l
        flag = "主窗已被边界污染" if depth > halo else "主窗仍干净"
        print(f"    layer {l}: 精确信息缺失深度 = {depth} 格 -> {flag}")
    print(f"  网络感受野半径 = 1 + L*R = {1 + L * Rr} 格 {1 + L*Rr} x 0.8λ ≈ "
          f"{(1 + L * Rr) * 0.8:.1f}λ；但输入只提供 {halo + 7 - 1} x {halo + 7 - 1} 格 "
          "的真实信息（13x13）。")


if __name__ == "__main__":
    import os
    import sys

    class _Tee:
        def __init__(self, *fs):
            self.fs = fs

        def write(self, s):
            for f in self.fs:
                f.write(s)

        def flush(self):
            for f in self.fs:
                f.flush()

    _log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "verify_khoram_report.txt"), "w", encoding="utf-8")
    _orig = sys.stdout
    sys.stdout = _Tee(_orig, _log)
    main()
    sys.stdout = _orig
    _log.close()
    print("report -> verify_khoram_report.txt")
