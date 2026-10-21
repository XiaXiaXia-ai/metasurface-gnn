# -*- coding: utf-8 -*-
"""eh_planes.py -- E-plane (phi=0) vs H-plane (phi=90) metrics for every model.

Incidence is x-polarised normal (E || x), so
    phi = 0   is the xz-plane  = E-plane (contains E and k)
    phi = 90  is the yz-plane  = H-plane (contains H and k)

Both planes are scored separately (and averaged), because they test different
physics: the E-plane probes the element pattern / obliquity, the H-plane probes
the polarisation projection of the aperture field.

Outputs: eh_metrics.csv, figs/eh_planes.png
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import common as C
import compare as CMP

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")


def stats(grid, meas, db, plane):
    out = {}
    for tag, lo, hi in (("6_60", 6.0, 60.0), ("0_90", 0.0, 89.5)):
        m = grid.cut(plane) & (grid.th >= lo) & (grid.th <= hi) & (meas > -30)
        out["r_%s" % tag] = float(np.corrcoef(db[m], meas[m])[0, 1])
        out["rmse_%s" % tag] = float(np.sqrt(np.mean((db[m] - meas[m]) ** 2)))
        out["bias_%s" % tag] = float(np.mean(db[m] - meas[m]))
    return out


def main():
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    models = CMP.build_models()
    base = [c for c in cases if c["name"] == "ff_10"][0]
    g, meas = base["grid"], base["meas"]

    rows = []
    for lab, fn in models:
        db = fn(g, base["f"], CMP.code_of(base["code"])).db
        e = stats(g, meas, db, 0)
        h = stats(g, meas, db, 90)
        rows.append(dict(model=lab,
                         rE_6_60=e["r_6_60"], rH_6_60=h["r_6_60"],
                         r_mean_6_60=0.5 * (e["r_6_60"] + h["r_6_60"]),
                         rE_0_90=e["r_0_90"], rH_0_90=h["r_0_90"],
                         r_mean_0_90=0.5 * (e["r_0_90"] + h["r_0_90"]),
                         rmseE=e["rmse_6_60"], rmseH=h["rmse_6_60"],
                         biasE=e["bias_6_60"], biasH=h["bias_6_60"]))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "eh_metrics.csv"), index=False, float_format="%.3f")
    pd.set_option("display.width", 220)
    print(df.round(2).to_string(index=False))

    # asymmetry of the measurement itself
    mE = g.cut(0) & (g.th >= 6) & (g.th <= 60)
    mH = g.cut(90) & (g.th >= 6) & (g.th <= 60)
    print("\nmeasured band mean (6-60):  E-plane %.2f dBsm   H-plane %.2f dBsm   H-E = %+.2f dB"
          % (meas[mE].mean(), meas[mH].mean(), meas[mH].mean() - meas[mE].mean()))

    # ------------------------------------------------------------------ figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    COL = {"M0_AF": "#1f77b4", "M0b_AF_vector": "#5b9bd5", "M1_AF+element": "#2e7d32",
           "M1b_AF+airy": "#66bb6a", "M3_RS": "#6a1b9a", "M4_AS_paper": "#8e24aa",
           "M4c_AS_cos": "#ab47bc", "M2_PO_fitted": "#c62828", "M2n_PO_nominal": "#ef5350",
           "M6_phase_compress": "#795548", "M6b_DDA_coupled": "#a1887f"}
    order = list(dict(models))
    th = np.arange(0.0, 89.6, 0.5)

    def cut(vals, phi):
        m = g.cut(phi) & (g.th < 89.5)
        return np.interp(th, g.th[m], vals[m])

    fig = plt.figure(figsize=(15.6, 10.2))
    gs = fig.add_gridspec(3, 4, hspace=0.30, wspace=0.30)
    for i, lab in enumerate(order):
        r_, c_ = divmod(i, 4)
        db = dict(models)[lab](g, base["f"], CMP.code_of(base["code"])).db
        ax = fig.add_subplot(gs[r_, c_], projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_thetamin(-90)
        ax.set_thetamax(90)
        a = np.radians(th)
        # E-plane on the right, H-plane on the left, both CST + model
        ax.plot(a, np.clip(cut(meas, 0), -30, 15), color="#1565c0", lw=1.5, alpha=0.8, zorder=3)
        ax.plot(a, np.clip(cut(db, 0), -30, 15), color=COL[lab], lw=1.4, zorder=2)
        ax.plot(-a, np.clip(cut(meas, 90), -30, 15), color="#1565c0", lw=1.5, alpha=0.8, zorder=3)
        ax.plot(-a, np.clip(cut(db, 90), -30, 15), color=COL[lab], lw=1.4, ls=(0, (5, 2)), zorder=2)
        ax.set_ylim(-30, 15)
        ax.set_rticks([-30, -20, -10, 0, 10], labels=["", "", "", "", ""])
        ax.set_thetagrids([-90, -60, -30, 0, 30, 60, 90],
                          labels=["90", "60", "30", "0", "30", "60", "90"], fontsize=7)
        ax.grid(color="0.75", lw=0.5, ls=(0, (4, 3)))
        ax.set_title("%s\nE: r=%.2f   H: r=%.2f   (6-60%s)"
                     % (lab, df.set_index("model").loc[lab, "rE_6_60"],
                        df.set_index("model").loc[lab, "rH_6_60"], "\u00b0"),
                     fontsize=8, pad=10)
    ax = fig.add_subplot(gs[2, 3])
    ax.axis("off")
    ax.plot([0.02, 0.20], [0.90, 0.90], color="#1565c0", lw=1.5,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.24, 0.90, "CST", fontsize=8, va="center", transform=ax.transAxes)
    ax.plot([0.02, 0.20], [0.82, 0.82], color="#c62828", lw=1.4,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.24, 0.82, "theory", fontsize=8, va="center", transform=ax.transAxes)
    ax.plot([0.02, 0.20], [0.74, 0.74], color="0.2", lw=1.4,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.24, 0.74, "solid = E-plane", fontsize=8, va="center", transform=ax.transAxes)
    ax.plot([0.02, 0.20], [0.66, 0.66], color="0.2", lw=1.4, ls=(0, (5, 2)),
            transform=ax.transAxes, clip_on=False)
    ax.text(0.24, 0.66, "dashed = H-plane", fontsize=8, va="center", transform=ax.transAxes)
    ax.text(0.0, 0.56,
            "right half  = E-plane (phi = 0):\n"
            "              xz-plane, contains E and k\n"
            "left  half  = H-plane (phi = 90):\n"
            "              yz-plane, contains H and k\n\n"
            "theta = 0 (specular) at the top,\n"
            "theta = 90 at both ends; only the\n"
            "reflected wave (theta <= 90) is drawn\n\n"
            "radius: total sigma in dB(m^2)\n"
            "        -30 at the rim, +15 at the centre\n\n"
            "r = Pearson r over theta = 6-60 deg",
            fontsize=7.4, va="top", transform=ax.transAxes)
    cax = fig.add_axes([0.938, 0.12, 0.009, 0.62])
    cax.set_ylim(-30, 15)
    cax.set_xlim(0, 1)
    cax.set_xticks([])
    cax.set_yticks([-30, -20, -10, 0, 10])
    cax.tick_params(labelsize=7, length=3)
    cax.yaxis.set_label_position("right")
    cax.yaxis.tick_left()
    cax.set_ylabel("total  \u03c3   dB(m\u00b2)", fontsize=8, labelpad=8)
    cax.spines["top"].set_visible(False)
    cax.spines["bottom"].set_visible(False)
    fig.suptitle("E-plane (right, phi=0) and H-plane (left, phi=90), reflected wave only:"
                 " CST vs every model", fontsize=11, y=0.955)
    fig.savefig(os.path.join(FIG, "eh_planes.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("\nwrote eh_metrics.csv and figs/eh_planes.png")


if __name__ == "__main__":
    main()
