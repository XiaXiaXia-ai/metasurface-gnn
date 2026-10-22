# -*- coding: utf-8 -*-
"""量化：曲面的 z 分量对远场有多大影响？normal_z 一个标量能补回来吗？

    python curvature_check.py

只读调用 msgnn.physics.radiation（numpy 参考实现），不改任何源码。
"""
import sys

import numpy as np

sys.path.insert(0, r"D:/GNN/gnn")
from msgnn.physics import radiation as R          # noqa: E402

N, P, F = 20, 14.0, 10.0
lam = R.lam_mm(F)
k = 2 * np.pi / lam

x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
xy = np.stack([X.ravel(), Y.ravel()], axis=1)
pos_planar = np.concatenate([xy, np.zeros((N * N, 1))], axis=1)

q1 = np.ones(N * N, dtype=complex)
th = np.array([0.0])
ph = np.array([0.0])


def db(pos, q):
    e1, e2 = R.farfield_numpy(q, th, ph, F, P, pos, "vector")
    return float(R.to_db(R.sigma_from_fields(e1, e2))[0])


print("(1) 平面口径, q≡1            : %+8.4f dBsm   <- 19.342 自检" % db(pos_planar, q1))

# --- 沿 x 弯成 60° 圆柱：弧长 20P = 280 mm, R = 280/rad(60°)
half = np.radians(30.0)
Rc = (N * P) / (2 * half)
s = X.ravel()                                   # 弧长坐标
psi = s / Rc                                    # 每列的法向偏角
xc = Rc * np.sin(psi)
zc = Rc * (np.cos(psi) - 1.0)                   # 中间最高，两边下垂
pos_curv = np.stack([xc, Y.ravel(), zc], axis=1)
nz = np.cos(psi)                                # normal_z = cos(psi)
print("(2) 圆柱, q≡1（真实 3-D 位置）: %+8.4f dBsm   <- 相位失配" % db(pos_curv, q1))

# --- 若把 z 去掉（回到平面近似，正是当前 build_graph 干的事）
pos_curv_flat = np.stack([xc, Y.ravel(), np.zeros_like(zc)], axis=1)
print("(3) 圆柱但 z 填 0（平面近似） : %+8.4f dBsm   <- 当前代码等价于此" % db(pos_curv_flat, q1))

# --- 若用 z 做相位补偿（说明"缺的就是 z"）
q_comp = np.exp(-1j * k * zc)
print("(4) 圆柱 + 按 z 补偿相位      : %+8.4f dBsm   <- z 就是缺的那块信息" % db(pos_curv, q_comp))

print()
print("几何量：R = %.1f mm, 边缘下垂 |z| = %.1f mm = %.2f λ, 相位差 %.0f°"
      % (Rc, abs(zc.min()), abs(zc.min()) / lam, 360 * abs(zc.min()) / lam))
print("口径投影：chord/arc = %.4f  ->  仅面积损失 %.2f dB"
      % (2 * Rc * np.sin(half) / (N * P), 20 * np.log10(2 * Rc * np.sin(half) / (N * P))))

# --- normal_z 的歧义：同一 n_z 对应两个不同的位置/高度
print()
print("normal_z 的歧义：psi=±30° 两个单元 n_z 都 = %.4f，但 z 相同、x 相反" % np.cos(half))
print("               psi=+30° (x=%+.1f) 与 psi=-30° (x=%+.1f) 只能靠 x 区分"
      % (Rc * np.sin(half), -Rc * np.sin(half)))
print("               而 n_z 相同的两个曲面可以曲率不同：z=R(cos psi-1) vs z=-R(psi^2/2)（抛物线），")
print("               在顶点处 z、n_z 全同，但离焦行为不同。")
