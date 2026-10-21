# -*- coding: utf-8 -*-
"""How far is the solved 1-bit array from the ideal coding model, and why?

Compares the measured 10 GHz far field of the 2x2 baseline (D:\ff_er265_r2_b2)
with the ideal 1-bit model built from the isolated-cell reflection coefficients
(r = 4.7 mm -> -1.24 dB / -5.3 deg, r = 2.0 mm -> -1.39 dB / +174.6 deg):

    sqrt(sigma)(theta,phi) = 2*sqrt(pi)/lambda * cos(theta) * A_cell
                             * sum_n gamma_n exp(j k (x_m u + y_n v))

For a uniform aperture (all gamma = 1) this reduces to 4*pi*A^2/lambda^2, i.e.
the PEC-plate reference used everywhere else in this project.  Only the
reflection half space (theta <= 90 deg) is used.

Reports the broadside gap, the co-pol pattern correlation, and the coherent
fraction implied by the residual (which bounds the in-array 1-bit phase error
if that is the mechanism).
"""
import numpy as np

FF = r"D:\ff_er265_r2_b2\ff_10.txt"
CODE = ("1101010001", "0001000000", "0011110101", "0000101101", "0001000100",
        "1100110011", "1111100000", "0010000110", "1011111011", "1010111001")
P, N, LAM, BLOCK = 14.0, 20, 29.9792458, 2
PLATE_DB = 19.34
Acell = P * P
CONST = 2.0 * np.sqrt(np.pi) / LAM * Acell * 1e-3   # 1/mm * mm^2 * m/mm -> m

G0 = 10 ** (-1.24 / 20) * np.exp(1j * np.radians(-5.3))
G1 = 10 ** (-1.39 / 20) * np.exp(1j * np.radians(174.6))

bits = np.array([[int(c) for c in r] for r in CODE])
code = np.repeat(np.repeat(bits, BLOCK, 0), BLOCK, 1)
g = np.where(code == 0, G0, G1).ravel()
x = (np.arange(N) - (N - 1) / 2.0) * P
X, Y = np.meshgrid(x, x, indexing="ij")

d = np.loadtxt(FF)
th, ph = d[:, 0], d[:, 1]
k = 2 * np.pi / LAM
total = 10 * np.log10(10 ** (d[:, 2] / 10) + 10 ** (d[:, 4] / 10))
front = th <= 90.0

print("measured specular      : %7.2f dBsm" % total[(th == 0) & (ph == 0)][0])
print("measured mean (10..90) : %7.2f dBsm"
      % (10 * np.log10(np.mean(10 ** (total[front & (th >= 10)] / 10)))))
print("specular - mean        : %7.2f dB" % (total[0] - 10 * np.log10(
    np.mean(10 ** (total[front & (th >= 10)] / 10)))))

T = np.radians(th[front]); Pp = np.radians(ph[front])
Psi = k * (np.outer(np.sin(T) * np.cos(Pp), X.ravel())
           + np.outer(np.sin(T) * np.sin(Pp), Y.ravel()))
E = CONST * np.cos(T) * (np.exp(1j * Psi) @ g)
ideal = 20 * np.log10(np.abs(E) + 1e-30)
print("ideal-model specular   : %7.2f dBsm" % ideal[0])
print("broadside gap          : %7.2f dB" % (total[front][0] - ideal[0]))
print("ideal-model mean       : %7.2f dBsm"
      % (10 * np.log10(np.mean(10 ** (ideal[th[front] >= 10] / 10)))))

thf, ttf = th[front], total[front]
ethf = 10 ** (d[front, 2] / 10)
for pc in (0, 45, 90):
    m = (ph[front] == pc) & (thf >= 6) & (thf <= 60) & (ttf > -30)
    c = np.corrcoef(ttf[m], ideal[m])[0, 1]
    c2 = np.corrcoef(10 * np.log10(ethf[m]), ideal[m])[0, 1]
    print("pattern corr phi=%3d deg: total %.3f | co-pol %.3f  (%d samples)"
          % (pc, c, c2, m.sum()))

rad = 10 ** ((total[front][0] - PLATE_DB) / 20.0)
print("\nresidual / PEC amplitude = %.3f  (%.2f dB below the plate)"
      % (rad, total[front][0] - PLATE_DB))
dphi = 2 * np.degrees(np.arccos(np.clip(rad / abs(G0), -1, 1)))
print("if the residual were a pure phase error: in-array 1-bit phase = %.1f deg "
      "(design 180 deg)" % dphi)
