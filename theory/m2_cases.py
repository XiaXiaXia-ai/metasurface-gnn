# -*- coding: utf-8 -*-
"""m2_cases.py -- M2 (PO two-region, |Gamma_gap| fitted) against CST, case by case.

M2 has the highest 2-D correlation under the 0-90 deg standard (rho = 0.913) but is
13.1 dB too dim overall.  Both facts have to be visible, so the catalogue keeps the
ABSOLUTE dBsm scale (no normalisation); a bias-corrected overlay is added at the end
to show that the *shape* is what the correlation is measuring.

Outputs
-------
figs/m2_cases_polar.png  7 cases, CST-style upper-half polar, E right / H left
figs/m2_cases_cuts.png   E/H cuts in Cartesian form + the bias-corrected overlay
m2_cases.csv             per-case rho_E / rho_H / rho_2D / bias / RMSE
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import common as C
import compare as CMP
import models as M

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")
EDGE = 89.5


def rr(a, b, m):
    if m.sum() < 8:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])


def main():
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    ggap = CMP.FIT["gamma_gap"]
    print("M2 uses gamma_gap = %.3f angle %.1f deg" % (abs(ggap), np.degrees(np.angle(ggap))))

    for c in cases:
        g = c["grid"]
        c["m2"] = M.po_two_region(g, c["f"], CMP.code_of(c["code"]), gamma_gap=ggap).db
        base = (g.th < EDGE) & (c["meas"] > -30)
        c["r2D"] = rr(c["m2"], c["meas"], base)
        c["rE"] = rr(c["m2"], c["meas"], base & g.cut(0))
        c["rH"] = rr(c["m2"], c["meas"], base & g.cut(90))
        c["bias"] = float(np.mean(c["m2"][base] - c["meas"][base]))
        c["rmse"] = float(np.sqrt(np.mean((c["m2"][base] - c["meas"][base]) ** 2)))
        print("  %-9s  r2D %.3f  rE %.3f  rH %.3f  bias %+6.2f dB  rmse %5.2f"
              % (c["name"], c["r2D"], c["rE"], c["rH"], c["bias"], c["rmse"]))
    pd.DataFrame([{k: c[k] for k in ("name", "f", "code", "r2D", "rE", "rH", "bias", "rmse")}
                  for c in cases]).to_csv(os.path.join(HERE, "m2_cases.csv"),
                                          index=False, float_format="%.3f")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    RED, BLUE = "#c62828", "#1565c0"
    th = np.arange(0.0, 89.6, 0.5)

    def cut(vals, g, phi):
        m = g.cut(phi) & (g.th < EDGE)
        return np.interp(th, g.th[m], vals[m])

    # ------------------------------------------------------------ polar figure
    fig = plt.figure(figsize=(15.6, 8.6))
    gs = fig.add_gridspec(2, 4, hspace=0.30, wspace=0.30)
    for i, c in enumerate(cases):
        r_, c_ = divmod(i, 4)
        g = c["grid"]
        ax = fig.add_subplot(gs[r_, c_], projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_thetamin(-90)
        ax.set_thetamax(90)
        a = np.radians(th)
        # right half E-plane, left half H-plane
        ax.plot(a, np.clip(cut(c["meas"], g, 0), -30, 15), color=BLUE, lw=1.5, alpha=0.8, zorder=3)
        ax.plot(a, np.clip(cut(c["m2"], g, 0), -30, 15), color=RED, lw=1.4, zorder=2)
        ax.plot(-a, np.clip(cut(c["meas"], g, 90), -30, 15), color=BLUE, lw=1.5, alpha=0.8, zorder=3)
        ax.plot(-a, np.clip(cut(c["m2"], g, 90), -30, 15), color=RED, lw=1.4, ls=(0, (5, 2)), zorder=2)
        ax.set_ylim(-30, 15)
        ax.set_rticks([-30, -20, -10, 0, 10], labels=["", "", "", "", ""])
        ax.set_thetagrids([-90, -60, -30, 0, 30, 60, 90],
                          labels=["90", "60", "30", "0", "30", "60", "90"], fontsize=7)
        ax.grid(color="0.75", lw=0.5, ls=(0, (4, 3)))
        ax.set_title("%s\n$\\rho_{2D}$=%.3f  $\\rho_E$=%.2f  $\\rho_H$=%.2f  bias %+.1f dB"
                     % (c["name"], c["r2D"], c["rE"], c["rH"], c["bias"]), fontsize=8, pad=9)
    ax = fig.add_subplot(gs[1, 3])
    ax.axis("off")
    ax.plot([0.02, 0.24], [0.88, 0.88], color=BLUE, lw=1.5, transform=ax.transAxes, clip_on=False)
    ax.text(0.28, 0.88, "CST", fontsize=8, va="center", transform=ax.transAxes)
    ax.plot([0.02, 0.24], [0.80, 0.80], color=RED, lw=1.4, transform=ax.transAxes, clip_on=False)
    ax.text(0.28, 0.80, "M2 PO (fit)", fontsize=8, va="center", transform=ax.transAxes)
    ax.text(0.0, 0.70,
            "M2 PO two-region, |Gamma_gap| fitted\n"
            "  Gamma_gap = %.2f angle %.0f deg\n\n"
            "  right half: E-plane (phi = 0)\n"
            "  left  half: H-plane (phi = 90)\n"
            "  solid / dashed = same split for M2\n\n"
            "  radius: total sigma, dB(m^2)\n"
            "          -30 at the rim, +15 centre\n"
            "  NOTE the absolute scale: M2 sits\n"
            "  ~13 dB below CST almost everywhere,\n"
            "  which is what drives bias = -13.1 dB\n"
            "  even though rho_2D = 0.913."
            % (abs(ggap), np.degrees(np.angle(ggap))),
            fontsize=7.2, va="top", transform=ax.transAxes)
    fig.suptitle("M2 PO (two-region, fitted) vs CST -- 7 cases, absolute dB scale, "
                 "reflected wave only", fontsize=11, y=0.96)
    fig.savefig(os.path.join(FIG, "m2_cases_polar.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------ cut figure
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.3))
    c0 = [c for c in cases if c["name"] == "ff_10"][0]
    g = c0["grid"]
    for ax, phi, tag in ((axes[0], 0, "E-plane ($\\phi$=0)"), (axes[1], 90, "H-plane ($\\phi$=90)")):
        m = g.cut(phi) & (g.th < EDGE) & (c0["meas"] > -30)
        ax.plot(g.th[m], c0["meas"][m], "o-", color=BLUE, ms=2.4, lw=1.0, label="CST")
        ax.plot(g.th[m], c0["m2"][m], "-", color=RED, lw=1.4, label="M2 PO")
        ax.set_xlabel("$\\theta$ (deg)")
        ax.set_ylabel("total $\\sigma$ (dBsm)")
        ax.set_title("%s   $\\rho$ = %.3f   bias = %+.1f dB"
                     % (tag, rr(c0["m2"], c0["meas"], m), np.mean(c0["m2"][m] - c0["meas"][m])),
                     fontsize=9)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_xlim(0, 90)
        top = float(max(c0["meas"][m].max(), c0["m2"][m].max()))
        ax.set_ylim(top - 45, top + 4)
    ax = axes[2]
    m = g.cut(0) & (g.th < EDGE) & (c0["meas"] > -30)
    bias = float(np.mean(c0["m2"][m] - c0["meas"][m]))
    ax.plot(g.th[m], c0["meas"][m], "o-", color=BLUE, ms=2.4, lw=1.0, label="CST")
    ax.plot(g.th[m], c0["m2"][m], "-", color=RED, lw=1.2, alpha=0.55, label="M2 PO (raw)")
    ax.plot(g.th[m], c0["m2"][m] - bias, "--", color=RED, lw=1.4,
            label="M2 PO shifted %+.1f dB" % (-bias))
    ax.set_xlabel("$\\theta$ (deg)")
    ax.set_title("E-plane, with the constant bias removed:\nthe shape is what $\\rho$ rewards",
                 fontsize=9)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7.5)
    ax.set_xlim(0, 90)
    top = float(max(c0["meas"][m].max(), (c0["m2"][m] - bias).max()))
    ax.set_ylim(top - 45, top + 4)
    fig.suptitle("M2 PO (fitted) vs CST at 10 GHz, $\\phi$ cuts", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "m2_cases_cuts.png"), dpi=140)
    plt.close(fig)
    print("\nwrote figs/m2_cases_polar.png, figs/m2_cases_cuts.png, m2_cases.csv")


if __name__ == "__main__":
    main()
