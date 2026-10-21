# -*- coding: utf-8 -*-
"""explore.py -- data sanity checks for the theory suite (diagnostic only)."""
import numpy as np

FF1 = r"D:\ff_er265_r2_b2\ff_10.txt"
FF2 = r"D:\dataset\results\ff\ff_0000.txt"
FF3 = r"D:\dataset\results\ff\ff_0001.txt"
CODE = ("1101010001", "0001000000", "0011110101", "0000101101", "0001000100",
        "1100110011", "1111100000", "0010000110", "1011111011", "1010111001")
P, N, BLOCK = 14.0, 20, 2
LAM = 299.792458 / 10.0
A = (N * P * 1e-3) ** 2
PLATE = 10 * np.log10(4 * np.pi * A**2 / (LAM * 1e-3) ** 2)

d = np.loadtxt(FF1)
th, ph = d[:, 0], d[:, 1]
eth, eph = d[:, 2], d[:, 4]
tot = 10 * np.log10(10 ** (eth / 10) + 10 ** (eph / 10))
T = np.unique(th); Pp = np.unique(ph)
G = tot.reshape(T.size, Pp.size)
print("grid", T.size, Pp.size, "plate %.3f dBsm" % PLATE)

# --- specular / the exact doc numbers
print("\n[1] reproduced doc numbers")
print("  specular (0,0)          %8.3f" % G[0, 0])
front = th <= 90
m10 = front & (th >= 10)
print("  mean 10..90 (linear)    %8.3f" % (10 * np.log10(np.mean(10 ** (tot[m10] / 10)))))
print("  mean 10..90 (dB mean)   %8.3f" % np.mean(tot[m10]))
g0 = 10 ** (-1.24 / 20) * np.exp(1j * np.radians(-5.3))
g1 = 10 ** (-1.39 / 20) * np.exp(1j * np.radians(174.6))
bits = np.array([[int(c) for c in r] for r in CODE])
code = np.repeat(np.repeat(bits, BLOCK, 0), BLOCK, 1)
print("  ones fraction           %8.3f (%d/100)" % (bits.mean(), bits.sum()))
gam = np.where(code == 0, g0, g1).ravel()
x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")
k = 2 * np.pi / LAM
CST = 2 * np.sqrt(np.pi) / LAM * (P * P) * 1e-3
u = np.sin(np.radians(th)) * np.cos(np.radians(ph))
v = np.sin(np.radians(th)) * np.sin(np.radians(ph))
E = np.zeros_like(u, dtype=complex)
for i in range(0, u.size, 8192):
    sl = slice(i, min(i + 8192, u.size))
    psi = k * (np.outer(u[sl], X.ravel()) + np.outer(v[sl], Y.ravel()))
    E[sl] = np.exp(1j * psi) @ gam
mod = 20 * np.log10(np.abs(CST * np.cos(np.radians(th)) * E) + 1e-30)
print("  M0 specular             %8.3f" % mod[0])
print("  M0 mean 10..90          %8.3f" % (10 * np.log10(np.mean(10 ** (mod[m10] / 10)))))
print("  gap                     %8.3f" % (tot[0] - mod[0]))

# --- lobes
print("\n[2] lobe shapes")
for tag, mask in (("front", th <= 90), ("back", th > 90)):
    idx = np.where(mask)[0]
    pk = idx[np.argmax(tot[idx] * 0 + G.ravel()[idx])]
    print("  %s peak %.3f dBsm at (%.0f,%.0f)" % (tag, G.ravel()[pk], th[pk], ph[pk]))
back = (th > 90)
print("  back theta=180         %8.3f" % G[-1, 0])
# back lobe width along phi=0
cut = G[-1::-1, 0]  # theta 180 -> 0
i180 = 0
lvl = cut - cut[0]
print("  back cut theta=180->150:", np.round(cut[:31], 1))
# -3 dB width of back lobe
w = np.where(cut > cut[0] - 3)[0]
print("  back -3dB half-width ~ %.1f deg" % (w.max() + 1))
cf = G[:91, 0]
print("  front phi=0 theta 0..20:", np.round(cf[:21], 2))
w = np.where(cf > cf.max() - 3)[0]
print("  front peak %.2f at %d deg; -3dB span %s" % (cf.max(), cf.argmax(), (w.min(), w.max())))

# --- polarisation
print("\n[3] polarisation / phi dependence")
for t0 in (0, 10, 20, 30, 45, 60, 75):
    i = int(np.argmin(abs(T - t0)))
    row = G[i]
    print("  th=%3d  tot phi0 %7.2f  phi45 %7.2f  phi90 %7.2f  phi135 %7.2f  min/max over phi %7.2f/%7.2f"
          % (T[i], row[0], row[45], row[90], row[135], row.min(), row.max()))
print("  cross-pol eth-eph at phi=0, th=0/30/60/90:",
      np.round([G[0, 0] - eph[0], 0, 0, 0], 1))
for t0 in (0, 30, 60, 90):
    i = int(np.argmin(abs(T - t0)))
    j = 0
    print("    th=%2d phi=0  Eth %7.2f  Eph %7.2f  ratio %6.1f dB" % (T[i], eth[i], eph[i], eth[i] - eph[i]))

# --- two codes
print("\n[4] two codes (2 deg grid)")
a = np.loadtxt(FF2); b = np.loadtxt(FF3)
ta, pa = a[:, 0], a[:, 1]
ta_tot = 10 * np.log10(10 ** (a[:, 2] / 10) + 10 ** (a[:, 3] / 10))
tb_tot = 10 * np.log10(10 ** (b[:, 2] / 10) + 10 ** (b[:, 3] / 10))
print("  specular A/B  %.3f / %.3f  diff %.3f" % (ta_tot[0], tb_tot[0], tb_tot[0] - ta_tot[0]))
mm = (ta >= 6) & (ta <= 60)
print("  corr(A,B) dB over 6..60 deg (all phi)  %.3f" % np.corrcoef(ta_tot[mm], tb_tot[mm])[0, 1])
print("  rms(A-B) over 6..60 deg                %.2f dB" % np.sqrt(np.mean((ta_tot[mm] - tb_tot[mm]) ** 2)))
print("  mean 10..90 A/B %.3f / %.3f" % (10 * np.log10(np.mean(10 ** (ta_tot[(ta >= 10)] / 10))),
                                          10 * np.log10(np.mean(10 ** (tb_tot[(ta >= 10)] / 10)))))
# code 0001 ones fraction
c1 = "1011101110000001100110000000101011000110001011000110010111001101001000010000110110111001011011011100"
b1 = np.array([int(c) for c in c1]).reshape(10, 10)
print("  code0001 ones fraction %.3f   code0000 %.3f" % (b1.mean(), bits.mean()))
print("  code0001 hamming vs 0000: %d" % (b1 != bits).sum())

# --- the common mode required per frequency
print("\n[5] required common-mode weight per freq (from specular)")
for f in ("9.8", "9.9", "10", "10.1", "10.2"):
    dd = np.loadtxt(r"D:\ff_er265_r2_b2\ff_%s.txt" % f)
    tt = 10 * np.log10(10 ** (dd[:, 2] / 10) + 10 ** (dd[:, 4] / 10))
    lam = 299.792458 / float(f)
    plate = 10 * np.log10(4 * np.pi * A**2 / (lam * 1e-3) ** 2)
    r = 10 ** ((tt[0] - plate) / 20)
    print("  f=%4s  spec %7.3f  plate %6.3f  |a|/plate %.4f  -> dphi %6.1f deg"
          % (f, tt[0], plate, r, 2 * np.degrees(np.arccos(np.clip(r / 0.86, -1, 1)))))
