# -*- coding: utf-8 -*-
"""样本可区分性优先的码本设计：随机 vs 结构化。

判据不是绝对物理精度，而是「不同码产生的方向图差异是否足够大」——
用已标定的正向模型（M1 + 共同模）对每个码算方向图，再统计：
    - 峰值方向分布（有多少个码的波束离开了轴向）
    - 两两方向图相关（越低越可分）
    - 峰值电平与主瓣宽度
"""
import json
import numpy as np

N, P = 20, 14.0
LAM = 29.9792458
K = 2 * np.pi / LAM
G0 = 0.867 * np.exp(1j * np.radians(-5.3))
G1 = 0.852 * np.exp(1j * np.radians(174.6))
B = 0.37 * np.exp(1j * np.radians(270.0))
Q, SCALE = -0.40, 1.11

th = np.arange(0, 61, 2.0)
ph = np.arange(0, 360, 4.0)
T, Pp = np.meshgrid(th, ph, indexing="ij")
T, Pp = T.ravel(), Pp.ravel()
U = np.sin(np.radians(T)) * np.cos(np.radians(Pp))
V = np.sin(np.radians(T)) * np.sin(np.radians(Pp))
TILT = SCALE * np.cos(np.radians(T)) ** Q
x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
KER = np.exp(1j * K * (np.outer(U, X.ravel()) + np.outer(V, Y.ravel())))
print("grid %d angles x %d cells" % (T.size, X.size))


def pattern(bits):
    """bits: (N,N) 0/1 -> dB pattern (normalised), peak location."""
    w = np.where(bits == 0, G0 + B, G1 + B)
    E = (w.ravel() @ KER.T) * TILT
    p = np.abs(E) ** 2
    db = 10 * np.log10(p / p.max() + 1e-12)
    k = int(np.argmax(p))
    return db, T[k], Pp[k], 10 * np.log10(p.max())


def ramp(theta0, phi0=0.0):
    t = np.radians(theta0)
    ph0 = K * (X * np.sin(t) * np.cos(np.radians(phi0)) + Y * np.sin(t) * np.sin(np.radians(phi0)))
    return (np.cos(ph0) < 0).astype(int)


def multi(theta_a, theta_b, phi_a=0.0, phi_b=180.0):
    t1, t2 = np.radians(theta_a), np.radians(theta_b)
    p1 = K * (X * np.sin(t1) * np.cos(np.radians(phi_a)) + Y * np.sin(t1) * np.sin(np.radians(phi_a)))
    p2 = K * (X * np.sin(t2) * np.cos(np.radians(phi_b)) + Y * np.sin(t2) * np.sin(np.radians(phi_b)))
    z = np.exp(1j * p1) + np.exp(1j * p2)
    return (np.cos(np.angle(z)) < 0).astype(int)


def checker(block):
    i = np.arange(N) // block
    return ((i[:, None] + i[None, :]) % 2).astype(int)


rng = np.random.default_rng(20261021)
codes = {}
for k in range(20):
    codes["rand_%02d" % k] = (rng.random((N, N)) < 0.5).astype(int)
for t0 in (10, 20, 30, 40, 50):
    for p0 in (0, 90):
        codes["ramp_%d_%d" % (t0, p0)] = ramp(t0, p0)
for pair in ((15, 15), (20, 30), (10, 40)):
    codes["multi_%d_%d" % pair] = multi(pair[0], pair[1])
for b in (2, 4, 5):
    codes["check_%d" % b] = checker(b)

names = list(codes)
pats = {}
print("\n%-12s %8s %6s %8s" % ("code", "peakTh", "peakPh", "peak dB"))
for nm in names:
    db, pt, pp, pk = pattern(codes[nm])
    pats[nm] = db
    print("%-12s %8.0f %6.0f %8.2f" % (nm, pt, pp, pk))

M = np.array([pats[n] for n in names])
C = np.corrcoef(M)
iu = np.triu_indices(len(names), 1)
off = C[iu]

print("\n pairwise pattern correlation (all pairs, n=%d pairs):" % off.size)
print("   min %.2f  p10 %.2f  median %.2f  p90 %.2f  max %.2f"
      % (off.min(), np.percentile(off, 10), np.median(off), np.percentile(off, 90), off.max()))

rand = [i for i, n in enumerate(names) if n.startswith("rand")]
Ci = C[np.ix_(rand, rand)][np.triu_indices(len(rand), 1)]
print(" random-only subset: median %.2f  p90 %.2f  (n=%d pairs)" % (np.median(Ci), np.percentile(Ci, 90), Ci.size))

for fam in ("ramp", "multi", "check"):
    sel = [i for i, n in enumerate(names) if n.startswith(fam)]
    cc = C[np.ix_(rand, sel)]
    print(" family %-6s (%2d codes): 与随机码的最大相关 均值 %.2f / 最坏 %.2f"
          % (fam, len(sel), cc.max(axis=0).mean(), cc.max(axis=0).max()))
mix = [i for i, n in enumerate(names) if not n.startswith("rand")]
cc = C[np.ix_(rand, mix)]
print(" 随机 vs 结构化 全体: 相关 中位 %.2f  p90 %.2f  (越低越互补)"
      % (np.median(cc), np.percentile(cc, 90)))

json.dump({k: v.tolist() for k, v in codes.items()}, open("D:/GNN/design/codebook_demo.json", "w"))
print("\ncodebook -> D:/GNN/design/codebook_demo.json  (%d codes)" % len(codes))
