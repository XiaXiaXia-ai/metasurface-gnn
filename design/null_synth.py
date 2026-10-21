# -*- coding: utf-8 -*-
"""用直接二元搜索 (DBS) 试做 1-bit 零陷：理想单元 vs 实测单元。

问题：阵中两态不是严格反相（实测均值 0.37 的共同模），这份"直流"在口径上
是一个不可控的均匀分量，它会在 θ=0 处留下底座。零陷到底还能做多深？

cost = P_null / P_peak   (+ 少量区外抑制)，在 400 bit 上逐位翻转。
"""
import numpy as np

N, P = 20, 14.0
LAM = 29.9792458
K = 2 * np.pi / LAM

# 两种单元模型
G_IDEAL = (1.0 * np.exp(1j * 0.0), 1.0 * np.exp(1j * np.pi))
B_IDEAL = 0.0
G_MEAS = (0.867 * np.exp(1j * np.radians(-5.3)), 0.852 * np.exp(1j * np.radians(174.6)))
B_MEAS = 0.37 * np.exp(1j * np.radians(270.0))

# 角度网格
th = np.arange(0, 61, 1.0)
ph = np.arange(0, 360, 2.0)
T, Pp = np.meshgrid(th, ph, indexing="ij")
T, Pp = T.ravel(), Pp.ravel()
U = np.sin(np.radians(T)) * np.cos(np.radians(Pp))
V = np.sin(np.radians(T)) * np.sin(np.radians(Pp))

x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
PH = np.exp(1j * K * (np.outer(U, X.ravel()) + np.outer(V, Y.ravel())))   # (nang, 400)
print("angles %d, cells %d, kernel %.0f MB" % (T.size, X.size, PH.nbytes / 1e6))

main = T <= 5.0
null = (np.abs(T - 20.0) < 2.0) & ((np.abs(Pp - 0.0) < 10) | (np.abs(Pp - 180.0) < 10))
outside = (T > 6.0) & ~null & (T < 45.0)
print("main %d, null %d, outside %d" % (main.sum(), null.sum(), outside.sum()))


def cost(E):
    p = np.abs(E) ** 2
    peak = p[main].mean()
    return p[null].max() / peak + 0.02 * p[outside].mean() / peak


def dbs(gamma, b, sweeps=12, seed=3):
    rng = np.random.default_rng(seed)
    state = rng.integers(0, 2, X.size)
    w = np.where(state == 0, gamma[0] + b, gamma[1] + b)
    E = w @ PH.T
    c = cost(E)
    for s in range(sweeps):
        improved = 0
        order = rng.permutation(X.size)
        for n in order:
            w_new = (gamma[1] if state[n] == 0 else gamma[0]) + b
            d = w_new - w[n]
            E2 = E + d * PH[:, n]
            c2 = cost(E2)
            if c2 < c - 1e-12:
                state[n] = 1 - state[n]
                w[n] = w_new
                E, c = E2, c2
                improved += 1
        if improved == 0:
            break
    p = np.abs(E) ** 2
    peak = 10 * np.log10(p[main].mean())
    return dict(state=state, cost=c,
                null_db=10 * np.log10(p[null].max() / p[main].mean()),
                null_mean_db=10 * np.log10(p[null].mean() / p[main].mean()),
                out_db=10 * np.log10(p[outside].mean() / p[main].mean()),
                ones=int(state.sum()), peak=peak)


for name, g, b in (("理想 +-1（无直流）", G_IDEAL, B_IDEAL), ("实测单元（含 0.37 共同模）", G_MEAS, B_MEAS)):
    r = dbs(g, b)
    print("\n== %s ==" % name)
    print("   1 的个数 %3d   主瓣电平(相对) %.1f dB" % (r["ones"], 0.0))
    print("   零陷(最差)  %.1f dBc     零陷(均值) %.1f dBc" % (r["null_db"], r["null_mean_db"]))
    print("   区外均值    %.1f dBc     cost %.3e" % (r["out_db"], r["cost"]))
