# -*- coding: utf-8 -*-
"""Cross-validate the 'uniform coherent background' found by the theory study.

The theory report fits, for the 2x2 baseline, a uniform additive background
b (complex) on top of the ideal array factor:

    E = C * cos(theta) * ( S_code + b * S_uniform )

and finds b = 0.366 at phase 265 deg, 90 deg away from the coding term.  With
TWO parameters that fit is nearly always possible, so the real question is:
does the same b also describe OTHER random codes?

Test: fit b on case 0000 (1 deg, complex), then apply that b unchanged to
cases 0001..0003 (2 deg, magnitude only), and also fit each case separately.

If the fitted phase is stable across codes -> real code-independent common mode.
If it scatters -> the 265 deg 'orthogonality' is an artefact of a 2-parameter fit.
"""
import json
import sys

import numpy as np

sys.path.insert(0, r"D:\GNN\theory")
import common as C

F = 10.0
N, P = 20, 14.0
k = 2 * np.pi / C.lam_mm(F)
xs = (np.arange(N) - (N - 1) / 2.0) * P
CONST = C.const_C(F)
G0 = 1.0 * np.exp(1j * np.radians(-5.3))
G1 = 1.0 * np.exp(1j * np.radians(174.6))


def load_case(i):
    if i == 0:
        d = np.loadtxt(r"D:\ff_er265_r2_b2\ff_10.txt")
        m = d[:, 0] <= 90
        th, ph = d[m, 0], d[m, 1]
        meas = 10 * np.log10(10 ** (d[m, 2] / 10) + 10 ** (d[m, 4] / 10))
        code10 = "".join(C.CODE_BASE)
    else:
        d = np.loadtxt(r"D:\dataset\results\ff\ff_%04d.txt" % i)
        th, ph = d[:, 0], d[:, 1]
        meas = 10 * np.log10(10 ** (d[:, 2] / 10) + 10 ** (d[:, 3] / 10))
        code10 = json.load(open(r"D:\dataset\results\res_%04d.json" % i))["code"]
    cmap, bits = C.code_from_string(code10)
    return dict(th=th, ph=ph, meas=meas, cmap=cmap, bits=bits, n=int(bits.sum()))


def prep(case):
    t = np.radians(case["th"])
    u, v = np.sin(t) * np.cos(np.radians(case["ph"])), np.sin(t) * np.sin(np.radians(case["ph"]))
    gam = C.gamma_map(case["cmap"], (G0, G1))
    S_code = C.aperture_sum(gam, u, v, k, xs)
    S_uni = C.aperture_sum(np.ones((N, N), complex), u, v, k, xs)
    case.update(u=u, v=v, S=S_code, U=S_uni, tilt=CONST * np.cos(t))
    case["mask"] = (case["th"] >= 6) & (case["th"] <= 60) & (case["meas"] > -30)


def evaluate(case, b):
    E = case["tilt"] * (case["S"] + b * case["U"])
    pred = 20 * np.log10(np.abs(E) + 1e-30)
    m = case["mask"]
    rmse = float(np.sqrt(np.mean((pred[m] - case["meas"][m]) ** 2)))
    spec = float(pred[np.argmin(np.abs(case["th"])) ])
    return rmse, spec, pred


def fit_b(case, phases=None, mags=None):
    phases = np.arange(0, 360, 5.0) if phases is None else phases
    mags = np.arange(0, 0.62, 0.02) if mags is None else mags
    m = case["mask"]
    best = (1e9, 0, 0)
    for mag in mags:
        for deg in phases:
            b = mag * np.exp(1j * np.radians(deg))
            pred = 20 * np.log10(np.abs(case["tilt"] * (case["S"] + b * case["U"])) + 1e-30)
            r = float(np.sqrt(np.mean((pred[m] - case["meas"][m]) ** 2)))
            if r < best[0]:
                best = (r, mag, deg)
    # refine
    r0, mag0, deg0 = best
    for mag in np.arange(max(0, mag0 - 0.02), mag0 + 0.021, 0.005):
        for deg in np.arange(deg0 - 5, deg0 + 5.1, 1.0):
            b = mag * np.exp(1j * np.radians(deg))
            pred = 20 * np.log10(np.abs(case["tilt"] * (case["S"] + b * case["U"])) + 1e-30)
            r = float(np.sqrt(np.mean((pred[m] - case["meas"][m]) ** 2)))
            if r < best[0]:
                best = (r, mag, deg)
    return best


cases = {i: load_case(i) for i in (0, 1, 2, 3)}
for c in cases.values():
    prep(c)

print("case  ones/100  measured spec  mean(10-90)   b=0 RMSE   fitted |b|  arg b   RMSE@fit")
fits = {}
for i, c in cases.items():
    r0, s0, _ = evaluate(c, 0.0)
    r, mag, deg = fit_b(c)
    fits[i] = (mag, deg)
    mean_far = 10 * np.log10(np.mean(10 ** (c["meas"][(c["th"] >= 10)] / 10)))
    sp = c["meas"][np.argmin(np.abs(c["th"]))]
    print(" %d     %3d      %7.2f      %7.2f     %6.2f      %6.3f   %5.1f    %5.2f"
          % (i, c["n"], sp, mean_far, r0, mag, deg, r))

print("\ntransfer: fit b on case 0, apply to the others")
b0 = fits[0][0] * np.exp(1j * np.radians(fits[0][1]))
print("  b0 = %.3f ang %.1f deg" % (fits[0][0], fits[0][1]))
print(" case   spec_meas  spec_pred   RMSE   RMSE_noB   delta")
for i, c in cases.items():
    r, s, _ = evaluate(c, b0)
    r0, s0, _ = evaluate(c, 0.0)
    sp = c["meas"][np.argmin(np.abs(c["th"]))]
    print("  %d     %7.2f    %7.2f   %6.2f   %6.2f   %6.2f" % (i, sp, s, r, r0, r0 - r))

print("\nphase scan at fixed |b| matching the specular of case 0 (check 142 vs 265):")
c0 = cases[0]
for deg in (85.0, 142.0, 180.0, 265.0):
    # pick |b| that lands on the measured specular (bisection on magnitude)
    lo, hi = 0.0, 1.5
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        _, s, _ = evaluate(c0, mid * np.exp(1j * np.radians(deg)))
        if s < 10.798:
            lo = mid
        else:
            hi = mid
    mag = 0.5 * (lo + hi)
    r, s, _ = evaluate(c0, mag * np.exp(1j * np.radians(deg)))
    print("   arg b = %5.1f deg  |b| = %.3f  spec = %6.2f  RMSE = %.2f" % (deg, mag, s, r))
