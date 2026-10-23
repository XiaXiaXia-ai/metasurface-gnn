"""
khoram_minimal.py
=================
Khoram et al., ACS Photonics 2023 的最小可运行复刻（纯 torch，不依赖 DGL / PyG）。
目的：把论文的架构与官方代码用 ~150 行讲清楚，并打印每一层的张量形状与参数量。

对照来源
  - 论文：DOI 10.1021/acsphotonics.2c01019
  - 官方：erfan6511/GNN-for-Metasurfaces  training/model_p3.py + pol3_code.py
  - 复现：aarowz/metasurface-modernized-gnn  src/models/custom_gnn.py

运行：python khoram_minimal.py
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

# ============================================================================
# 0  超参数（全部来自官方 pol3_code.py 的常量）
# ============================================================================
R          = 3          # connection radius，单位=格
WS         = 7          # window_size：主窗 7x7
PD         = 6          # pd_size = 2R：外扩补边
N          = WS + 2 * PD          # 19 -> 19x19 = 361 节点
NG         = 24         # 每个单元胞 24x24 子像素
IN_D       = 5          # [R, H, Dx, Dy, bnd]
H_D        = 1600       # 隐层宽度
OUT_D      = 6 * NG * NG  # 3456 = 该单元上方的 (6, 24, 24) 场块
NHL        = 5          # 隐层数 -> 总层数 = 1 + 5 + 1 = 7


def circle_offsets(r):
    """圆邻域偏移，顺序必须与官方代码的 k 外层 / l 内层 遍历一致。"""
    return [(k, l) for k in range(-r, r + 1) for l in range(-r, r + 1)
            if k * k + l * l <= r * r]


OFFS = circle_offsets(R)          # 29 个
K    = len(OFFS)


# ============================================================================
# 1  图构建：把 19x19 的格点映射成 29 邻域索引表
# ============================================================================
def build_graph(n, offs):
    """
    返回
      nbr   : (n*n, K) long，第 t 列是 "偏移 offs[t] 处的邻居节点号"，越界为 -1
      valid : (n*n,) bool，邻域是否完整（官方语义：不完整 -> 该节点输出置零）
      rinv  : (K,) float，1/r，自环 r=0.5
    """
    ids = torch.arange(n * n).view(n, n)
    pad = torch.full((n + 2 * R, n + 2 * R), -1, dtype=torch.long)
    pad[R:R + n, R:R + n] = ids

    nbr = torch.empty(n * n, K, dtype=torch.long)
    for t, (k, l) in enumerate(offs):
        # 节点 (i,j) 的第 t 个邻居 = pad[i+R+k, j+R+l]
        nbr[:, t] = pad[R + k:R + k + n, R + l:R + l + n].reshape(-1)

    valid = (nbr >= 0).all(dim=1)

    rinv = torch.empty(K)
    for t, (k, l) in enumerate(offs):
        d = (k * k + l * l) ** 0.5
        rinv[t] = 1.0 / (0.5 if d == 0 else d)
    return nbr, valid, rinv


# ============================================================================
# 2  GNN 层：论文 Eq.(1)
#    z_v^{l+1} = f( sum_{u in N(v)+v}  W_u * z_u / r_uv )
#    实现 = 邻居按固定顺序拼接 -> 一个 (K*Cin, Cout) 的大矩阵 -> 激活
# ============================================================================
class KhoramLayer(nn.Module):
    def __init__(self, c_in, c_out, bias=True, act=False):
        super().__init__()
        self.c_in, self.c_out = c_in, c_out
        self.W = nn.Parameter(torch.empty(K * c_in, c_out))
        nn.init.xavier_uniform_(self.W, gain=nn.init.calculate_gain('relu') if act else 1.0)
        self.b = nn.Parameter(torch.zeros(1, c_out)) if bias else None
        self.act = act

    def forward(self, h, nbr, valid, rinv):
        # h: (n*n, c_in) -> 取 29 个邻居 -> (n*n, K, c_in)
        hm = h[nbr.clamp_min(0)] * rinv.view(1, K, 1)     # 先除距离（可被 W 吸收）
        out = hm.reshape(-1, K * self.c_in) @ self.W      # 拼接 + 一次大矩阵乘
        if self.b is not None:
            out = out + self.b
        if self.act:
            out = F.leaky_relu(out)                       # 官方是 LeakyReLU，不是论文写的 ReLU
        return out * valid.unsqueeze(1)                   # 邻域不完整 -> 整行置零


class GNN(nn.Module):
    """1 输入层 + 5 隐层 + 1 输出层 = 7 层（论文正文说 6 层）"""
    def __init__(self):
        super().__init__()
        layers = [KhoramLayer(IN_D, H_D, bias=True, act=False)]
        layers += [KhoramLayer(H_D, H_D, bias=True, act=True) for _ in range(NHL)]
        layers += [KhoramLayer(H_D, OUT_D, bias=True, act=False)]
        self.layers = nn.ModuleList(layers)

    def forward(self, x, nbr, valid, rinv):
        for L in self.layers:
            x = L(x, nbr, valid, rinv)
        return x


# ============================================================================
# 3  拼接：7x7 个节点 x 3456 维 -> (6, 168, 168)
#    忠实复刻官方那段最绕的 reshape：.reshape(WS*WS, NG*NG, 6).T.reshape(6,NG,NG)
# ============================================================================
def stitch(node_out, mask):
    o = node_out[mask]                       # (7*7, 3456)
    o = o.view(WS * WS, NG * NG, 6).permute(2, 0, 1)     # (6, 49, 576)
    img = o.reshape(6, WS, WS, NG, NG)                   # cell=(x,y) -> (6, x, y, px, py)
    img = img.permute(0, 1, 3, 2, 4)                     # (6, x, px, y, py)
    return img.reshape(6, WS * NG, WS * NG).unsqueeze(0)  # (1, 6, 168, 168)


# ============================================================================
# 4  修缝 CNN：4 层 5x5，6->24->48->24->6，前三层 ReLU，末层线性
# ============================================================================
class SeamCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv2d(6, 24, 5, padding='same')
        self.c2 = nn.Conv2d(24, 48, 5, padding='same')
        self.c3 = nn.Conv2d(48, 24, 5, padding='same')
        self.c4 = nn.Conv2d(24, 6, 5, padding='same')

    def forward(self, x):
        x = F.relu(self.c1(x))
        x = F.relu(self.c2(x))
        x = F.relu(self.c3(x))
        return self.c4(x)


# ============================================================================
# 5  主程序：跑一遍，打印形状与参数量
# ============================================================================
def n_params(m):
    return sum(p.numel() for p in m.parameters())


def main():
    torch.manual_seed(0)
    nbr, valid, rinv = build_graph(N, OFFS)

    print("=" * 70)
    print("图结构")
    print("=" * 70)
    print(f"  节点数            : {N}x{N} = {N*N}")
    print(f"  圆邻域偏移数 K     : {K}   (R={R})")
    print(f"  邻域完整节点数     : {int(valid.sum())}  "
          f"(= {int(valid.sum()**0.5)}x{int(valid.sum()**0.5)}，位于 [3,15]^2)")
    print(f"  仅主窗节点进入解码 : {WS}x{WS} = {WS*WS}")

    mask = torch.zeros(N, N, dtype=torch.bool)
    mask[PD:PD + WS, PD:PD + WS] = True
    mask = mask.reshape(-1)
    print(f"  主窗 mask 覆盖     : {int(mask.sum())} 个节点")

    print("\n" + "=" * 70)
    print("前向传播（形状追踪）")
    print("=" * 70)
    gnn, cnn = GNN(), SeamCNN()

    x = torch.randn(N * N, IN_D)
    print(f"  input                 {tuple(x.shape)}")

    h = x
    for i, L in enumerate(gnn.layers):
        h = L(h, nbr, valid, rinv)
        tag = "输入" if i == 0 else ("输出" if i == len(gnn.layers) - 1 else "隐层")
        print(f"  GCL{i+1:<2d} {tag:<4s}         {tuple(h.shape)}"
              f"   W={tuple(L.W.shape)}  {n_params(L):>12,}")

    img = stitch(h, mask)
    print(f"  stitch                {tuple(img.shape)}")

    out = cnn(img)
    print(f"  CNN 4x5x5             {tuple(out.shape)}")

    print("\n" + "=" * 70)
    print("参数量")
    print("=" * 70)
    print(f"  GNN   : {n_params(gnn):>14,}")
    print(f"  CNN   : {n_params(cnn):>14,}")
    print(f"  合计  : {n_params(gnn)+n_params(cnn):>14,}")
    print(f"  单样本输出元素 : {out.numel():,}  ({out.numel()*4/1024**2:.2f} MB fp32)")

    print("\n" + "=" * 70)
    print("与 PyG 复现版的对照")
    print("=" * 70)
    repl = (K * IN_D * 400) + 5 * (K * 400 * 400 + 400) + (K * 400 * 64)
    print(f"  本文件（官方架构）GNN : {n_params(gnn):>14,}")
    print(f"  复现版（h=400,out=64）: {repl:>14,}")
    print(f"  比值                  : {n_params(gnn)/repl:.1f}x")


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
                             "khoram_minimal_out.txt"), "w", encoding="utf-8")
    _orig = sys.stdout
    sys.stdout = _Tee(_orig, _log)
    main()
    sys.stdout = _orig
    _log.close()
