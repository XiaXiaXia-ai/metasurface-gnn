# -*- coding: utf-8 -*-
"""两个 0-CST 判别（2026-10-23）：
① 单实标量 g 乘 q0 的扫描 —— 若最优 g≈1.035，说明 M1 的全部内容就是幅度标定；
② 把 GAMMA_PH_DEG 改成 (-5.3, 218.7)（即阵中 224°）直接算 M0 —— 看镜面能否到 +10.8。
"""
import glob
import json
import os

import numpy as np

ROOT = r"D:\dataset"
FF = os.path.join(ROOT, "results", "ff")
RES = os.path.join(ROOT, "results")
P = 14.0
N = 20
LAM = 29.9792458
K = 2 * np.pi / LAM
C0 = 2 * np.sqrt(np.pi) / LAM * (P * P) * 1e-3      # sqrt(m^2)
PLATE = 19.34200583535118

# gamma sets to compare
G_FLOQUET = (0.867 * np.exp(1j * np.radians(-5.3)), 0.852 * np.exp(1j * np.radians(174.6)))
G_224 = (0.867 * np.exp(1j * np.radians(-5.3)), 0.852 * np.exp(1j * np.radians(218.7)))
G_224_1 = (1.002 * np.exp(1j * np.radians(-5.3)), 1.002 * np.exp(1j * np.radians(218.7)))

# angle grid (2 deg, 46 x 180)
th = np.arange(0, 91, 2.0)
ph = np.arange(0, 360, 2.0)
T, Ph = np.meshgrid(th, ph, indexing="ij")
T, Ph = T.ravel(), Ph.ravel()
U = np.sin(np.radians(T)) * np.cos(np.radians(Ph))
V = np.sin(np.radians(T)) * np.sin(np.radians(Ph))
pth = np.cos(np.radians(T)) * np.cos(np.radians(Ph))
pph = -np.sin(np.radians(Ph))

x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
PHS = np.exp(1j * K * (np.outer(U, X.ravel()) + np.outer(V, Y.ravel())))   # (8280, 400)

mask = (T >= 6.0) & (T <= 60.0)


def spec(q):
    s = q @ PHS.T
    e2 = (C0 ** 2) * (s.real ** 2 + s.imag ** 2) * (pth ** 2 + pph ** 2)
    return 10 * np.log10(np.maximum(e2, 1e-30))


def load(limit=120):
    out = []
    for f in sorted(glob.glob(os.path.join(FF, "ff_*.txt")))[:limit]:
        i = int(os.path.basename(f)[3:7])
        rj = os.path.join(RES, "res_%04d.json" % i)
        if not os.path.isfile(rj):
            continue
        rec = json.load(open(rj, encoding="utf-8"))
        d = np.loadtxt(f)
        meas = 10 * np.log10(10 ** (d[:, 2] / 10) + 10 ** (d[:, 3] / 10))
        bits = np.repeat(np.repeat(np.array([int(c) for c in rec["code"]]).reshape(10, 10), 2, 0), 2, 1)
        out.append((i, bits.ravel(), meas))
    return out


cases = load(120)
print("cases loaded:", len(cases))

# ---- ① gain scan
rows = []
for g in np.arange(0.90, 1.201, 0.01):
    res = []
    for i, b, meas in cases:
        q = np.where(b == 0, G_FLOQUET[0], G_FLOQUET[1]) * g
        pred = spec(q)
        m = mask & (meas > -30)
        res.append(np.sqrt(np.mean((pred[m] - meas[m]) ** 2)))
    rows.append((float(g), float(np.mean(res))))
best = min(rows, key=lambda r: r[1])
print("\n[1] gain scan (rmse over theta 6-60, %d cases):" % len(cases))
for g, r in rows:
    if abs(g * 100 - round(g * 100)) < 1e-9 and int(round(g * 100)) % 5 == 0:
        print("   g=%.2f  rmse=%6.3f dB" % (g, r))
print("   BEST g=%.3f  rmse=%.3f dB" % best)

# ---- ② specular under the three gamma sets
print("\n[2] specular (theta=0), mean over %d cases:" % len(cases))
for name, gam in (("floquet 180deg", G_FLOQUET), ("224deg |G|=0.867", G_224),
                  ("224deg |G|=1.002", G_224_1)):
    preds, meas_s = [], []
    for i, b, meas in cases:
        q = np.where(b == 0, gam[0], gam[1])
        preds.append(spec(q)[0])
        meas_s.append(meas[0])
    print("   %-18s predicted %+7.2f   measured %+7.2f   diff %+6.2f"
          % (name, np.mean(preds), np.mean(meas_s), np.mean(preds) - np.mean(meas_s)))
