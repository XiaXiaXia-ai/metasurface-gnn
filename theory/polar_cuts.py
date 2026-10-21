# -*- coding: utf-8 -*-
"""polar_cuts.py -- CST-style polar cuts of the reflected wave, one panel per model.

Layout follows the CST 2-D polar result view:

    * only the upper half is drawn: theta <= 90 deg is the wave reflected by the
      surface (theta > 90 is the back side of the PEC ground plane);
    * theta = 0 (specular) is at the TOP, theta = 90 at both the left and right end
      of the half disc, so the angle grows away from the top;
    * the right half is the phi = 0 cut and the left half is the mirror cut
      (phi = 180), like CST's "Phi=90 / Phi=270" two-sided plot;
    * radius = total sigma in dB(m^2) = dBsm, -30 at the rim to +15 at the centre;
    * simulation in blue, theory in colour, Pearson rho printed per panel.

Outputs
-------
figs/polar_all_phi0.png  11 models, mirror layout (phi 0 | 180)
figs/polar_all_EH.png    11 models, E-plane right / H-plane left (phi 0 | 90)
polar_rho.csv            rho per model per meridian
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import common as C
import compare as CMP

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")
DEG = "\u00b0"

COL = {"M0_AF": "#1f77b4", "M0b_AF_vector": "#5b9bd5", "M1_AF+element": "#2e7d32",
       "M1b_AF+airy": "#66bb6a", "M3_RS": "#6a1b9a", "M4_AS_paper": "#8e24aa",
       "M4c_AS_cos": "#ab47bc", "M2_PO_fitted": "#c62828", "M2n_PO_nominal": "#ef5350",
       "M6_phase_compress": "#795548", "M6b_DDA_coupled": "#a1887f"}


def rho(a, b, mask):
    if mask.sum() < 8:
        return np.nan
    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def polar_axis(fig, pos, th, m_r, m_l, c_r, c_l, col, title, rmin=-30.0, rmax=15.0):
    """Upper-half polar: theta = 0 at the top, +theta to the right, -theta to the left."""
    ax = fig.add_subplot(pos, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_thetamin(-90)
    ax.set_thetamax(90)
    a = np.radians(th)
    ax.plot(a, np.clip(m_r, rmin, rmax), color=col, lw=1.4, zorder=2)
    ax.plot(-a, np.clip(m_l, rmin, rmax), color=col, lw=1.4, zorder=2)
    ax.plot(a, np.clip(c_r, rmin, rmax), color="#1565c0", lw=1.5, alpha=0.80, zorder=3)
    ax.plot(-a, np.clip(c_l, rmin, rmax), color="#1565c0", lw=1.5, alpha=0.80, zorder=3)
    ax.set_ylim(rmin, rmax)
    ax.set_rticks([-30, -20, -10, 0, 10], labels=["", "", "", "", ""])
    ax.set_thetagrids([-90, -60, -30, 0, 30, 60, 90],
                      labels=["90", "60", "30", "0", "30", "60", "90"], fontsize=7)
    ax.grid(color="0.75", lw=0.5, ls=(0, (4, 3)))
    ax.spines["polar"].set_color("0.3")
    ax.set_title(title, fontsize=8.5, pad=11)
    return ax


def main():
    print("rebuilding model patterns ...")
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    models = CMP.build_models()
    base = [c for c in cases if c["name"] == "ff_10"][0]
    g, meas = base["grid"], base["meas"]
    fields = {lab: fn(g, base["f"], CMP.code_of(base["code"])) for lab, fn in models}
    order = list(fields)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    th = np.arange(0.0, 89.6, 0.5)   # theta=90 is degenerate for a cos(theta) aperture

    def cut(vals, phi):
        mask = g.cut(phi) & (g.th <= 90)
        return np.interp(th, g.th[mask], vals[mask])

    for fname, phi_l, ttl in (("polar_all_phi0.png", 180,
                               "mirror cut   phi = 0 (right)  |  phi = 180 (left)"),
                              ("polar_all_EH.png", 90,
                               "E-plane (right, phi = 0)  |  H-plane (left, phi = 90)")):
        fig = plt.figure(figsize=(15.6, 10.4))
        gs = fig.add_gridspec(3, 4, hspace=0.30, wspace=0.30)
        for i, lab in enumerate(order):
            r_, c_ = divmod(i, 4)
            mr, ml = cut(fields[lab].db, 0), cut(fields[lab].db, phi_l)
            cr, cl = cut(meas, 0), cut(meas, phi_l)
            # rho is always computed on the native 1 deg samples, never on the
            # 0.5 deg interpolation used only for drawing
            k60 = g.cut(0) & (g.th >= 6) & (g.th <= 60)
            r60 = rho(fields[lab].db, meas, k60 & (meas > -30))
            k0 = g.cut(0) & (g.th < 89.5)
            kl = g.cut(phi_l) & (g.th < 89.5)
            vr, vl = fields[lab].db[k0], fields[lab].db[kl]
            cr_, cl_ = meas[k0], meas[kl]
            keep = np.r_[(cr_ > -30), (cl_ > -30)]
            r90 = rho(np.r_[vr, vl], np.r_[cr_, cl_], keep)
            polar_axis(fig, gs[r_, c_], th, mr, ml, cr, cl, COL[lab],
                       "%s\n\u03c1 = %.3f  (6-60%s)     %.3f  (0-90%s)" % (lab, r60, DEG, r90, DEG))
        ax = fig.add_subplot(gs[2, 3])
        ax.axis("off")
        ax.plot([0.02, 0.22], [0.90, 0.90], color="#1565c0", lw=1.6, alpha=0.8,
                transform=ax.transAxes, clip_on=False)
        ax.text(0.26, 0.90, "Simulation (CST)", fontsize=8, va="center", transform=ax.transAxes)
        ax.plot([0.02, 0.22], [0.82, 0.82], color="#c62828", lw=1.4,
                transform=ax.transAxes, clip_on=False)
        ax.text(0.26, 0.82, "theory model", fontsize=8, va="center", transform=ax.transAxes)
        txt = ("CST-style polar cut\n"
               "  only \u03b8 = 0-90" + DEG + " is drawn: that is the\n"
               "  wave reflected by the surface\n"
               "  \u03b8 = 0 (specular) at the top, \u03b8 = 90 at both ends\n"
               "  right half: phi = 0     left half: phi = %d\n\n" % phi_l +
               "  radius: total \u03c3 in dB(m\u00b2) = dBsm\n"
               "          -30 at the rim, +15 at the centre\n"
               "          (scale bar at the right)\n\n"
               "\u03c1 = Pearson r of the dB cut\n"
               "  (6-60" + DEG + ")  pattern window used in the tables\n"
               "  (0-90" + DEG + ")  whole reflected hemisphere")
        ax.text(0.0, 0.72, txt, fontsize=7.4, va="top", transform=ax.transAxes)
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
        fig.suptitle("Reflected-wave polar cuts (\u03b8 \u2264 90" + DEG + "): every theory against CST"
                     "   --   " + ttl, fontsize=11, y=0.955)
        fig.savefig(os.path.join(FIG, fname), dpi=140, bbox_inches="tight")
        plt.close(fig)
        print("  wrote", fname)

    rows = []
    for lab in order:
        for pc in (0, 45, 90, 180):
            m = g.cut(pc) & (g.th < 89.5)
            rows.append(dict(model=lab, phi=pc,
                             rho_0_90=rho(fields[lab].db, meas, m & (meas > -30)),
                             rho_6_60=rho(fields[lab].db, meas,
                                          m & (g.th >= 6) & (g.th <= 60) & (meas > -30))))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "polar_rho.csv"), index=False, float_format="%.3f")
    print(df.pivot(index="model", columns="phi", values="rho_0_90").round(3).to_string())
    print("\ndone")


if __name__ == "__main__":
    main()
