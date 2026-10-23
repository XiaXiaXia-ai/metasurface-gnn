# -*- coding: utf-8 -*-
"""补充：三种 Gamma 在方向图层面的 rmse（theta 6-60）与镜面，并在 (Δφ, |Γ|) 上小网格扫描。"""
import glob, json, os
import numpy as np

ROOT = r"D:\dataset"; FF = os.path.join(ROOT, "results", "ff"); RES = os.path.join(ROOT, "results")
P, N, LAM = 14.0, 20, 29.9792458
K = 2 * np.pi / LAM
C0 = 2 * np.sqrt(np.pi) / LAM * (P * P) * 1e-3
th = np.arange(0, 91, 2.0); ph = np.arange(0, 360, 2.0)
T, Ph = np.meshgrid(th, ph, indexing="ij"); T, Ph = T.ravel(), Ph.ravel()
U = np.sin(np.radians(T)) * np.cos(np.radians(Ph)); V = np.sin(np.radians(T)) * np.sin(np.radians(Ph))
p2 = (np.cos(np.radians(T)) * np.cos(np.radians(Ph))) ** 2 + np.sin(np.radians(Ph)) ** 2
x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
PHS = np.exp(1j * K * (np.outer(U, X.ravel()) + np.outer(V, Y.ravel())))
mask = (T >= 6.0) & (T <= 60.0)

def load(limit=120):
    out = []
    for f in sorted(glob.glob(os.path.join(FF, "ff_*.txt")))[:limit]:
        i = int(os.path.basename(f)[3:7]); rj = os.path.join(RES, "res_%04d.json" % i)
        if not os.path.isfile(rj): continue
        rec = json.load(open(rj, encoding="utf-8")); d = np.loadtxt(f)
        meas = 10 * np.log10(10 ** (d[:, 2] / 10) + 10 ** (d[:, 3] / 10))
        bits = np.repeat(np.repeat(np.array([int(c) for c in rec["code"]]).reshape(10, 10), 2, 0), 2, 1)
        out.append((bits.ravel(), meas))
    return out

cases = load(120)

def evalu(gam0, gam1):
    r, s_pred, s_meas = [], [], []
    for b, meas in cases:
        q = np.where(b == 0, gam0, gam1)
        s = q @ PHS.T
        db = 10 * np.log10(np.maximum((C0 ** 2) * (s.real ** 2 + s.imag ** 2) * p2, 1e-30))
        m = mask & (meas > -30)
        r.append(np.sqrt(np.mean((db[m] - meas[m]) ** 2)))
        s_pred.append(db[0]); s_meas.append(meas[0])
    return float(np.mean(r)), float(np.mean(s_pred)), float(np.mean(s_meas))

print("%-22s %8s %9s %9s" % ("gamma set", "rmse", "spec_pred", "spec_meas"))
for name, a, b_ in (
    ("floquet 180 / 0.867", 0.867 * np.exp(1j * np.radians(-5.3)), 0.852 * np.exp(1j * np.radians(174.6))),
    ("224deg / 0.867", 0.867 * np.exp(1j * np.radians(-5.3)), 0.852 * np.exp(1j * np.radians(218.7))),
    ("224deg / 1.002", 1.002 * np.exp(1j * np.radians(-5.3)), 1.002 * np.exp(1j * np.radians(218.7))),
    ("224deg / 1.002, g=1.08", 1.082 * np.exp(1j * np.radians(-5.3)), 1.082 * np.exp(1j * np.radians(218.7))),
):
    r, sp, sm = evalu(a, b_)
    print("%-22s %8.3f %9.2f %9.2f" % (name, r, sp, sm))

print("\n(Delta_phi, |G|) grid  -- rmse / spec_pred")
best = None
for dphi in (150, 170, 180, 190, 200, 210, 224, 230, 240, 250):
    row = []
    for g in (0.95, 1.002, 1.05):
        a = g * np.exp(1j * np.radians(-5.3)); b_ = g * np.exp(1j * np.radians(-5.3 + dphi))
        r, sp, sm = evalu(a, b_)
        row.append("%5.2f/%5.1f" % (r, sp))
        if best is None or r < best[0]: best = (r, dphi, g, sp)
    print("  dphi=%3d  |G|=.95: %s  1.002: %s  1.05: %s" % (dphi, row[0], row[1], row[2]))
print("\nbest: rmse=%.3f at dphi=%d, |G|=%.3f (spec %.2f, meas %.2f)"
      % (best[0], best[1], best[2], best[3], sm))
