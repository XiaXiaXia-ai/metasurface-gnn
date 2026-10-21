# -*- coding: utf-8 -*-
"""Derive 1D cuts, 2D maps and beam metrics from the exported 3D farfields.

Everything downstream of the solver is computed from the single 3D export
(theta/phi grid with magnitude and phase), so no extra simulation is needed:

    1D cut   = one column of the grid  (fixed phi, sweep theta)
    2D map   = the same grid mapped to uv  (u = sin(theta)cos(phi))
    metrics  = peak direction, specular level, HPBW, first sidelobe

Usage:
    python postprocess_farfield.py [folder]

The folder defaults to D:\\ff_bg15 and must contain ff_*.txt files written by
export_farfield.py.  Results go to <folder>\\post\\.
"""
import glob
import os
import sys

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FOLDER = sys.argv[1] if len(sys.argv) > 1 else r"D:\ff_bg15"
CUT_PHIS = (0.0, 45.0, 90.0)   # 1D cuts to extract
FRONT_ONLY = True              # theta <= 90 deg (the reflecting hemisphere)


def load_ff(path):
    """Return (theta[], phi[], G[i_theta, i_phi]) with G in dB(m^2).

    Accepts both CST's native 8-column table (Abs(RCS) in column 2) and the
    6-column table written by export_farfield.py (theta/phi components only).
    """
    with open(path, "r", errors="replace") as fh:
        first = fh.readline()
    skip = 2 if "Theta" in first else 0
    d = np.loadtxt(path, skiprows=skip)
    if d.ndim != 2 or d.shape[1] < 5:
        raise ValueError("unexpected farfield table in %s" % path)
    th, ph = d[:, 0], d[:, 1]
    if d.shape[1] >= 8:
        rcs = d[:, 2]
    else:
        rcs = 10.0 * np.log10(10.0 ** (d[:, 2] / 10.0) + 10.0 ** (d[:, 4] / 10.0))
    ut, up = np.unique(th), np.unique(ph)
    g = np.full((ut.size, up.size), np.nan)
    g[np.searchsorted(ut, th), np.searchsorted(up, ph)] = rcs
    if np.isnan(g).any():
        print("   ! %d grid points missing" % int(np.isnan(g).sum()))
    return ut, up, g


def cut(ut, up, g, phi):
    j = int(np.argmin(np.abs(up - phi)))
    return ut, g[:, j]


def half_power_width(x, y):
    """HPBW in degrees around the maximum of the cut (x in deg, y in dB)."""
    i = int(np.argmax(y))
    def cross(step):
        k = i
        while 0 <= k + step < len(y) and y[k + step] > -3.0:
            k += step
        if not (0 <= k + step < len(y)):
            return None
        a, b = y[k], y[k + step]
        f = (-3.0 - a) / (b - a) if b != a else 0.0
        return abs(x[k] + f * (x[k + step] - x[k]) - x[i])
    left, right = cross(-1), cross(1)
    if left is None and right is None:
        return np.nan
    if left is None:
        return 2.0 * right
    if right is None:
        return 2.0 * left
    return left + right


def first_sidelobe(x, y):
    """Level and angle of the first sidelobe after the main lobe."""
    i = int(np.argmax(y))
    k = None
    for j in range(i + 1, len(y) - 1):
        if y[j] < y[j - 1] and y[j] <= y[j + 1]:
            k = j
            break
    if k is None:
        return np.nan, np.nan
    j = int(np.argmax(y[k:])) + k
    return y[j], x[j]


def metrics(ut, up, g):
    front = ut <= 90.0 if FRONT_ONLY else np.ones(ut.size, bool)
    gf = g[front, :]
    it, ip = np.unravel_index(np.nanargmax(gf), gf.shape)
    peak_db = gf[it, ip]
    peak_th, peak_ph = ut[front][it], up[ip]
    spec = g[np.argmin(np.abs(ut - 0.0)), np.argmin(np.abs(up - 0.0))]
    # at the pole every phi is degenerate, so cut through phi = 0
    cut_ph = 0.0 if peak_th < 1e-6 else peak_ph
    x, y = cut(ut, up, g, cut_ph)
    sel = (x <= 90.0) if FRONT_ONLY else np.ones(x.size, bool)
    hpbw = half_power_width(x[sel], y[sel])
    sll, sll_th = first_sidelobe(x[sel], y[sel])
    return dict(peak_db=peak_db, peak_theta=peak_th, peak_phi=peak_ph,
                specular_db=spec, suppression=peak_db - spec,
                hpbw=hpbw, sll_db=sll - peak_db, sll_theta=sll_th)


def plot_one(path, ut, up, g, met, outdir):
    stem = os.path.splitext(os.path.basename(path))[0]
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 5.0), facecolor="white")

    # --- 2D uv map ---
    sel = ut <= 90.0
    a = ax[0]
    if sel.sum() > 1:
        T, P = np.meshgrid(np.radians(ut[sel]), np.radians(up), indexing="ij")
        U, V = np.sin(T) * np.cos(P), np.sin(T) * np.sin(P)
        m = a.tricontourf(U.ravel(), V.ravel(), (g[sel, :] - met["peak_db"]).ravel(),
                          levels=np.arange(-40, 1, 2), cmap="jet", extend="min")
        fig.colorbar(m, ax=a, shrink=0.85, label="normalised (dB)")
    a.set_aspect("equal")
    a.set_xlim(-1, 1)
    a.set_ylim(-1, 1)
    a.set_xlabel("u = sinθcosφ")
    a.set_ylabel("v = sinθsinφ")
    a.set_title("%s  |  2D uv map" % stem)

    # --- 1D cuts ---
    b = ax[1]
    for phi in CUT_PHIS:
        x, y = cut(ut, up, g, phi)
        m = (x <= 90.0) if FRONT_ONLY else np.ones(x.size, bool)
        b.plot(x[m], y[m] - met["peak_db"], label="φ = %g°" % phi, lw=1.4)
    b.axhline(-3, color="0.6", ls=":", lw=1)
    b.set_xlim(0, 90)
    b.set_ylim(-40, 2)
    b.grid(alpha=0.3)
    b.set_xlabel("θ (deg)")
    b.set_ylabel("normalised (dB)")
    b.set_title("1D cuts (peak = %.1f dBsm @ θ=%.0f°, φ=%.0f°)"
                % (met["peak_db"], met["peak_theta"], met["peak_phi"]))
    b.legend(fontsize=8)
    fig.tight_layout()
    out = os.path.join(outdir, stem + ".png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main():
    files = sorted(glob.glob(os.path.join(FOLDER, "ff_*.txt")))
    if not files:
        raise SystemExit("no ff_*.txt in %s (run export_farfield.py first)" % FOLDER)

    outdir = os.path.join(FOLDER, "post")
    os.makedirs(outdir, exist_ok=True)

    rows = []
    for path in files:
        ut, up, g = load_ff(path)
        met = metrics(ut, up, g)
        png = plot_one(path, ut, up, g, met, outdir)
        name = os.path.splitext(os.path.basename(path))[0]
        # PEC reference: sigma = 4*pi*A^2/lambda^2 with A = 0.28 m, sigma(10 GHz) = 19.34 dBsm
        try:
            f = float(name.replace("ff_", ""))
        except ValueError:
            f = 10.0
        plate = 19.34 + 20.0 * np.log10(f / 10.0)
        met["plate_db"] = plate
        met["reduction"] = met["specular_db"] - plate
        rows.append((name, met))
        print("%-8s %5.1f GHz  specular %6.2f dBsm  PEC %5.2f  reduction %6.2f dB  "
              "HPBW %5.1f deg  1st SLL %6.1f dB"
              % (name, f, met["specular_db"], plate, met["reduction"],
                 met["hpbw"], met["sll_db"]))
        print("         ->", png)

    csv = os.path.join(outdir, "summary.csv")
    with open(csv, "w", encoding="utf-8") as fh:
        fh.write("case,specular_db,pec_plate_db,reduction_db,peak_db,peak_theta,"
                 "peak_phi,hpbw_deg,sll_db,sll_theta\n")
        for name, m in rows:
            fh.write("%s,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.1f\n"
                     % (name, m["specular_db"], m["plate_db"], m["reduction"],
                        m["peak_db"], m["peak_theta"], m["peak_phi"], m["hpbw"],
                        m["sll_db"], m["sll_theta"]))
    print("\nsummary ->", csv)


if __name__ == "__main__":
    main()
