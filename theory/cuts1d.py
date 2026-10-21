# -*- coding: utf-8 -*-
"""cuts1d.py -- 1-D cut comparison (phi = 0/45/90) for every model + Pearson r.

Row 1 of figs/cuts1d.png : the three meridional cuts, CST vs all 11 models.
Row 2                    : Pearson r of those same cuts (grouped bars), plus the
                           same r computed over theta = 0..60 so that the effect
                           of including the specular spike is visible.
figs/corr1d_vs_phi.png    : r as a function of the meridian angle phi (0..355 in
                           5 deg steps) -- shows that "0.83 / 0.85 / 0.78" are just
                           three draws from a broad distribution.

Outputs: corr1d.csv (per model, per phi, per case) and cuts1d.csv (the cut data).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import common as C
import compare as CMP

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")

CUTS = (0, 45, 90)
TH_WIN = (6.0, 60.0)


def poars(a, b, mask):
    if mask.sum() < 8:
        return np.nan
    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def main():
    print("rebuilding model patterns ...")
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    models = CMP.build_models()
    base = [c for c in cases if c["name"] == "ff_10"][0]
    g, meas = base["grid"], base["meas"]

    # ---------------------------------------------------------- 1-D correlation
    rows = []
    for label, fn in models:
        for c in cases:
            fld = fn(c["grid"], c["f"], CMP.code_of(c["code"]))
            rec = dict(model=label, case=c["name"])
            for pc in CUTS:
                m = c["grid"].cut_nearest(pc) & (c["grid"].th >= TH_WIN[0]) & \
                    (c["grid"].th <= TH_WIN[1]) & (c["meas"] > -30)
                rec["r_phi%d" % pc] = poars(fld.db, c["meas"], m)
            m0 = (c["grid"].th >= 0) & (c["grid"].th <= 60) & (c["meas"] > -30) & c["grid"].cut(0)
            rec["r_phi0_0_60"] = poars(fld.db, c["meas"], m0)
            rec["n_phi0"] = int((c["grid"].cut(0) & (c["grid"].th >= TH_WIN[0]) &
                                 (c["grid"].th <= TH_WIN[1]) & (c["meas"] > -30)).sum())
            rows.append(rec)
    r1 = pd.DataFrame(rows)

    # ------------------------------------------- r vs phi (5 deg sweep, ff_10)
    sweep = []
    for label, fn in models:
        fld = fn(g, base["f"], CMP.code_of(base["code"]))
        for pc in range(0, 360, 5):
            m = g.cut(pc) & (g.th >= TH_WIN[0]) & (g.th <= TH_WIN[1]) & (meas > -30)
            sweep.append(dict(model=label, phi=pc, r=poars(fld.db, meas, m)))
    sw = pd.DataFrame(sweep)
    sw.to_csv(os.path.join(HERE, "corr1d_phi_sweep.csv"), index=False, float_format="%.4f")
    r1.to_csv(os.path.join(HERE, "corr1d.csv"), index=False, float_format="%.4f")

    summ = sw.groupby("model").r.agg(["mean", "std", "min", "max"]).sort_values("mean",
                                                                               ascending=False)
    print("\n=== 1-D correlation over 72 meridians (ff_10) ===")
    print(summ.round(3).to_string())
    print("\n=== the three canonical cuts (ff_10) ===")
    b = r1[r1.case == "ff_10"].set_index("model")[["r_phi0", "r_phi45", "r_phi90", "r_phi0_0_60"]]
    print(b.round(3).to_string())

    # ---------------------------------------------------------------- figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fam = {"M0": "#4c72b0", "M0b": "#4c72b0", "M1": "#55a868", "M1b": "#55a868",
           "M2": "#c44e52", "M2n": "#c44e52", "M3": "#8172b2", "M4": "#8172b2",
           "M4c": "#8172b2", "M6": "#937860", "M6b": "#937860"}
    style = {"M0_AF": "-", "M0b_AF_vector": "--", "M1_AF+element": "-", "M1b_AF+airy": "--",
             "M2_PO_fitted": "-", "M2n_PO_nominal": "--", "M3_RS": "-", "M4_AS_paper": ":",
             "M4c_AS_cos": "--", "M6_phase_compress": "-", "M6b_DDA_coupled": "--"}

    fields = {lab: fn(g, base["f"], CMP.code_of(base["code"])) for lab, fn in models}
    order = list(fields)

    fig = plt.figure(figsize=(13.6, 8.2))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.95], hspace=0.33, wspace=0.20)
    for k, pc in enumerate(CUTS):
        ax = fig.add_subplot(gs[0, k])
        m = g.cut(pc) & (g.th <= 70)
        ax.plot(g.th[m], meas[m], "k.", ms=3.0, zorder=5, label="CST")
        for lab in order:
            ax.plot(g.th[m], fields[lab].db[m], style[lab], color=fam[lab.split("_")[0]],
                    lw=0.9, alpha=0.85)
        ax.set_xlim(0, 70)
        ax.set_ylim(meas[m].max() - 45, meas[m].max() + 3)
        ax.set_xlabel("$\\theta$ (deg)")
        ax.set_ylabel("total $\\sigma$ (dBsm)" if k == 0 else "")
        ax.set_title("$\\phi$ = %d deg" % pc, fontsize=11)
        ax.grid(alpha=0.3)
        if k == 0:
            ax.legend(fontsize=7, loc="upper right", markerscale=1.5)

    ax = fig.add_subplot(gs[1, :])
    bb = r1[r1.case == "ff_10"].set_index("model").loc[order]
    y = np.arange(len(order))
    hatches = ("///", "", "...")
    for j, (pc, off) in enumerate(zip(CUTS, (-0.27, 0.0, 0.27))):
        ax.barh(y + off, bb["r_phi%d" % pc].values, height=0.25,
                color=[fam[l.split("_")[0]] for l in order],
                alpha=(0.55, 1.0, 0.75)[j], edgecolor="k", linewidth=0.4,
                hatch=hatches[j], label="$\\phi$ = %d$^\\circ$" % pc)
        for i, v in enumerate(bb["r_phi%d" % pc].values):
            ax.text(v + 0.008, i + off, "%.2f" % v, va="center", fontsize=7)
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Pearson r on the cut, $\\theta$ = 6..60$^\\circ$")
    ax.set_title("1-D Pearson correlation of the three meridians (10 GHz baseline)", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.suptitle("1-D cuts: every theoretical model against CST", fontsize=11)
    fig.savefig(os.path.join(FIG, "cuts1d.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)

    # ---- r vs phi
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    show = ["M0_AF", "M1_AF+element", "M0b_AF_vector", "M3_RS", "M6_phase_compress",
            "M2_PO_fitted", "M6b_DDA_coupled"]
    for lab in show:
        d = sw[sw.model == lab]
        ax.plot(d.phi, d.r, lw=1.0, color=fam[lab.split("_")[0]], label=lab,
                ls=style[lab], alpha=0.9)
    band = sw[sw.model.isin(["M0_AF", "M1_AF+element", "M3_RS", "M4_AS_paper",
                             "M1b_AF+airy", "M4c_AS_cos"])].groupby("phi").r.agg(["mean", "std"])
    ax.fill_between(band.index, band["mean"] - band["std"], band["mean"] + band["std"],
                    color="0.6", alpha=0.25, label="AF family mean $\\pm$ 1$\\sigma$")
    for pc in CUTS:
        ax.axvline(pc, color="0.85", lw=0.8, zorder=0)
    ax.set_xlabel("meridian $\\phi$ (deg)")
    ax.set_ylabel("Pearson r, $\\theta$ = 6..60$^\\circ$")
    ax.set_xlim(0, 355)
    ax.set_ylim(0.2, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=2, loc="lower right")
    ax.set_title("1-D correlation as a function of the cut azimuth (10 GHz)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "corr1d_vs_phi.png"), dpi=140)
    plt.close(fig)
    print("\nwrote figs/cuts1d.png, figs/corr1d_vs_phi.png, corr1d.csv, corr1d_phi_sweep.csv")


if __name__ == "__main__":
    main()
