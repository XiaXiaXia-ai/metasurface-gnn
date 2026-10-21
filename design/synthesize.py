# -*- coding: utf-8 -*-
"""1-bit 编码超表面的波束调制：赋形 / 零陷的合成原型。

模型（已用 CST 标定，见 D:/GNN/theory）：
    w_n = Gamma_bit + b,  Gamma = {0.867 exp(-j5.3 deg), 0.852 exp(j174.6 deg)}
    b   = 0.37 exp(j270 deg)        # 阵中共同模（与编码无关的均匀分量）
    E(u,v) = cos^q(theta) * FFT(w),  q = -0.40,  scale = 1.11  (只在可见区、theta<75deg 内使用)

合成：Gerchberg-Saxton 交替投影 + 二进制投影。
"""
import numpy as np

N, P = 20, 14.0
LAM = 29.9792458
G0 = 0.867 * np.exp(1j * np.radians(-5.3))
G1 = 0.852 * np.exp(1j * np.radians(174.6))
B = 0.37 * np.exp(1j * np.radians(270.0))
Q, SCALE = -0.40, 1.11

NFFT = 256
DU = LAM / (NFFT * P)
K = np.arange(NFFT) - NFFT // 2
U = K * DU
UU, VV = np.meshgrid(U, U, indexing="ij")
RHO = np.hypot(UU, VV)
VIS = (RHO <= 1.0) & (RHO >= 0.0)
TH = np.degrees(np.arcsin(np.clip(RHO, 0, 1)))
TILT = np.where(RHO <= np.sin(np.radians(75)), SCALE * np.cos(np.radians(TH)) ** Q, 0.0)
VIS = TILT > 0
PHI = np.degrees(np.arctan2(VV, UU))


def place(w):
    a = np.zeros((NFFT, NFFT), complex)
    o = (NFFT - N) // 2
    a[o:o + N, o:o + N] = w
    return a


def farfield(w):
    return np.fft.fftshift(np.fft.fft2(place(w))) * TILT


def project(v):
    c0, c1 = G0 + B, G1 + B
    return np.where(np.abs(v - c0) <= np.abs(v - c1), c0, c1)


def synth(target, iters=120, seed=7):
    rng = np.random.default_rng(seed)
    w = np.where(rng.random((N, N)) < 0.5, G0 + B, G1 + B)
    best = None
    for _ in range(iters):
        E = farfield(w)
        mag = np.abs(E)
        ph = np.ones_like(E)
        ok = VIS & (mag > 1e-9)
        ph[ok] = E[ok] / mag[ok]
        En = np.zeros_like(E)
        En[VIS] = ph[VIS] * target[VIS]
        back = np.fft.ifft2(np.fft.ifftshift(En))
        o = (NFFT - N) // 2
        w = project(back[o:o + N, o:o + N])
        P_ = np.abs(farfield(w)) ** 2
        db = 10 * np.log10(P_ / P_.max() + 1e-12)
        err = float(np.mean((db[VIS] - 20 * np.log10(target[VIS] + 1e-9)) ** 2))
        if best is None or err < best[0]:
            best = (err, w.copy())
    return best[1]


def stats(w):
    P_ = np.abs(farfield(w)) ** 2
    return P_, 10 * np.log10(P_ / P_.max() + 1e-12)


def halfwidth(db):
    row = NFFT // 2
    u = U
    line = db[row]
    ok = (u >= 0) & (u <= 0.9)
    idx = np.where(ok & (line <= -3))[0]
    return float(np.degrees(np.arcsin(u[idx[0]]))) if idx.size else float("nan")


# ---------------------------------------------------------------- 目标 1：平顶赋形
T1 = np.zeros((NFFT, NFFT))
cov = VIS & (RHO <= np.sin(np.radians(15.0)))
T1[cov] = 1.0
w1 = synth(T1, iters=120)
P1, db1 = stats(w1)
m_out = VIS & (RHO > np.sin(np.radians(20.0)))
print("== 赋形：theta <= 15deg 平顶 ==")
print("   覆盖区(0-15deg)  n=%5d  均值 %6.2f dB  p10 %6.2f  p90 %6.2f  最差 %7.2f"
      % (cov.sum(), db1[cov].mean(), np.percentile(db1[cov], 10), np.percentile(db1[cov], 90), db1[cov].min()))
print("   区外(>20deg)     n=%5d  均值 %6.2f dB  p90 %6.2f  最差 %7.2f"
      % (m_out.sum(), db1[m_out].mean(), np.percentile(db1[m_out], 90), db1[m_out].max()))
print("   覆盖区能量占比 : %.1f %%" % (100 * P1[cov].sum() / P1[VIS].sum()))
print("   覆盖区起伏     : %.2f dB (p90-p10)   -3dB 半宽 %.1f deg"
      % (np.percentile(db1[cov], 90) - np.percentile(db1[cov], 10), halfwidth(db1)))

# ---------------------------------------------------------------- 目标 2：零陷
T2 = np.exp(-(np.radians(TH) / np.radians(6.0)) ** 2)
T2[VIS & (np.abs(TH - 12.0) < 2.0)] = 0.0
T2[VIS & (np.abs(TH - 25.0) < 2.0) & (np.abs(np.abs(PHI) - 90) < 15)] = 0.0
w2 = synth(T2, iters=120)
P2, db2 = stats(w2)
null_ring = VIS & (np.abs(TH - 12.0) < 1.0)
null_side = VIS & (np.abs(TH - 25.0) < 1.0) & (np.abs(np.abs(PHI) - 90) < 8)
print("\n== 零陷：宽主瓣 + 12deg 环 + 25deg 两侧 ==")
print("   主瓣峰值(归一)           : %.2f dB" % db2[VIS & (TH < 3)].mean())
print("   12deg 环零深             : 均值 %.1f dB, 最深 %.1f dB" % (db2[null_ring].mean(), db2[null_ring].min()))
print("   25deg 侧向零深           : 均值 %.1f dB, 最深 %.1f dB" % (db2[null_side].mean(), db2[null_side].min()))
print("   主瓣 -3dB 半宽           : %.1f deg" % halfwidth(db2))

np.save("D:/GNN/design/w_flat.npy", w1)
np.save("D:/GNN/design/w_null.npy", w2)
print("\nsaved -> D:/GNN/design/w_flat.npy, w_null.npy")
