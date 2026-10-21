# -*- coding: utf-8 -*-
"""corr2d.py -- 2-D Pearson correlation between every model and the CST pattern.

Unlike the corr_phi0/45/90 columns of results.csv (three 1-D meridian cuts), this
uses *every* sample of the front-hemisphere pattern at once:

    r_2D = pearson( model_dB(theta,phi), cst_dB(theta,phi) )
           over theta in [0,90], all phi, samples with cst > -30 dB

and repeats it inside five theta bands so that one can see *where* a model wins:

    core   0 -  5 deg   the specular lobe (the 13.8 dB gap lives here)
    near   5 - 15 deg   the near-forward pedestal / first sidelobe
    mid   15 - 30 deg
    outer 30 - 60 deg
    far   60 - 90 deg

Both the dB-domain Pearson r (the report convention) and the linear-power
Pearson r (dominated by the bright samples) are written out.

Outputs: corr2d.csv, figs/corr2d_rank.png, figs/corr2d_bands.png
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import common as C
import compare as CMP

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")

BANDS = [("core", 0.0, 5.0), ("near", 5.0, 15.0), ("mid", 15.0, 30.0),
         ("outer", 30.0, 60.0), ("far", 60.0, 90.0)]


def pearson(a, b, mask):
    if mask.sum() < 8:
        return np.nan
    x, y = a[mask], b[mask]
    if x.std() < 1e-12 or y.std() < 1e-12:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def row(grid, meas, model_db):
    out = {}
    base = (grid.th >= 0.0) & (grid.th <= 90.0) & (meas > -30)
    out["r2d_all"] = pearson(model_db, meas, base)
    core = (grid.th >= 6.0) & (grid.th <= 60.0) & (meas > -30)
    out["r2d_6_60"] = pearson(model_db, meas, core)
    out["n_6_60"] = int(core.sum())
    out["n_all"] = int(base.sum())
    for name, lo, hi in BANDS:
        out["r_" + name] = pearson(model_db, meas, base & (grid.th >= lo) & (grid.th < hi))
    lin = base & (grid.th >= 6) & (grid.th <= 60)
    out["r_lin_6_60"] = pearson(10 ** (model_db[lin] / 10), 10 ** (meas[lin] / 10),
                                np.ones(lin.sum(), bool))
    return out


def main():
    print("rebuilding all model patterns ...")
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    models = CMP.build_models()

    rows = []
    for label, fn in models:
        for c in cases:
            fld = fn(c["grid"], c["f"], CMP.code_of(c["code"]))
            r = row(c["grid"], c["meas"], fld.db)
            rows.append(dict(model=label, case=c["name"], **r))
            print("  %-18s %-9s  r2D(all) %.3f   core %.3f  near %.3f  mid %.3f  outer %.3f  far %.3f"
                  % (label, c["name"], r["r2d_all"], r["r_core"], r["r_near"],
                     r["r_mid"], r["r_outer"], r["r_far"]))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "corr2d.csv"), index=False, float_format="%.4f")

    # ---------------------------------------------------------------- figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = df[df.case == "ff_10"].copy().sort_values("r2d_6_60", ascending=True)
    order = base.model.tolist()

    fam = {"M0": "#4c72b0", "M0b": "#4c72b0", "M1": "#55a868", "M1b": "#55a868",
           "M2": "#c44e52", "M2n": "#c44e52", "M3": "#8172b2", "M4": "#8172b2",
           "M4c": "#8172b2", "M6": "#937860", "M6b": "#937860", "MEASURED": "k"}
    cols = [fam.get(m.split("_")[0], "0.5") for m in order]

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4),
                             gridspec_kw={"width_ratios": [1.05, 1.0]})
    ax = axes[0]
    y = np.arange(len(order))
    ax.barh(y + 0.19, base.r2d_6_60.values, height=0.36, color=cols, alpha=0.95,
            label="$\\theta$ = 6-60$^\\circ$  (core, headline)")
    ax.barh(y - 0.19, base.r2d_all.values, height=0.36, color=cols, alpha=0.38,
            label="$\\theta$ = 0-90$^\\circ$  (full hemisphere)")
    for i, (v, w) in enumerate(zip(base.r2d_6_60.values, base.r2d_all.values)):
        ax.text(v + 0.010, i + 0.19, "%.3f" % v, va="center", fontsize=8)
        ax.text(w + 0.010, i - 0.19, "%.3f" % w, va="center", fontsize=7, color="0.35")
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=8)
    ax.set_xlim(0, 1.05)
    ax.axvline(1.0, color="k", lw=0.6)
    ax.set_xlabel("2-D Pearson r of the dB pattern (all $\\phi$ at once)")
    ax.set_title("(a) 2-D pattern correlation, 10 GHz baseline", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    ax.legend(fontsize=7, loc="lower right")

    ax = axes[1]
    Z = np.array([[base.loc[base.model == m, "r_" + b[0]].iloc[0] for b in BANDS] for m in order])
    im = ax.imshow(Z, cmap="RdYlGn", vmin=0.2, vmax=1.0, aspect="auto", origin="lower")
    ax.set_xticks(range(len(BANDS)))
    ax.set_xticklabels(["%s\n%d-%d$^\\circ$" % (b[0], b[1], b[2]) for b in BANDS], fontsize=8)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    for i in range(Z.shape[0]):
        for j in range(Z.shape[1]):
            if np.isfinite(Z[i, j]):
                ax.text(j, i, "%.2f" % Z[i, j], ha="center", va="center", fontsize=7.5)
    ax.set_title("(b) where: r by $\\theta$ band", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Pearson r")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "corr2d_rank.png"), dpi=140)
    plt.close(fig)

    # ---- per-frequency / per-code stability of the ranking
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4))
    labels = [m for m in order if m in ("M0_AF", "M1_AF+element", "M0b_AF_vector",
                                        "M3_RS", "M4_AS_paper", "M6_phase_compress",
                                        "M2_PO_fitted", "M6b_DDA_coupled")]
    for ax, case in zip(axes, ["ff_9.8", "ff_10", "case_0001"]):
        sub = df[df.case == case].set_index("model").loc[labels]
        y = np.arange(len(labels))
        ax.barh(y, sub.r2d_all.values, color=[fam.get(m.split("_")[0], "0.5") for m in labels],
                alpha=0.9)
        for i, v in enumerate(sub.r2d_all.values):
            ax.text(v + 0.012, i, "%.3f" % v, va="center", fontsize=7.5)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7.5)
        ax.set_xlim(0, 1.02)
        ax.set_title(case, fontsize=10)
        ax.set_xlabel("2-D Pearson r")
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle("stability of the 2-D correlation across frequency and code", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "corr2d_bands.png"), dpi=140)
    plt.close(fig)

    # ---- scatter of the two extreme cases
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    for ax, m in zip(axes, ["M0_AF", "M1_AF+element", "M6_phase_compress"]):
        c = [x for x in cases if x["name"] == "ff_10"][0]
        fld = dict(models)[m](c["grid"], c["f"], CMP.code_of(c["code"]))
        g = c["grid"]
        msk = (g.th <= 60) & (c["meas"] > -30)
        ax.plot(c["meas"][msk], fld.db[msk], ".", ms=1.2, alpha=0.25, color=fam.get(m.split("_")[0], "0.5"))
        lim = [max(-45, c["meas"][msk].min()), c["meas"][msk].max() + 2]
        ax.plot(lim, lim, "k-", lw=0.8)
        r = pearson(fld.db, c["meas"], msk)
        ax.set_title("%s   r = %.3f" % (m, r), fontsize=9)
        ax.set_xlabel("CST total $\\sigma$ (dBsm)")
        ax.set_ylabel("model (dBsm)")
        ax.grid(alpha=0.25)
    fig.suptitle("model vs CST, $\\theta \\leq$ 60 deg, all $\\phi$ (10 GHz baseline)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "corr2d_scatter.png"), dpi=140)
    plt.close(fig)

    print("\nwrote corr2d.csv, figs/corr2d_rank.png, figs/corr2d_bands.png, figs/corr2d_scatter.png")
    print("\nranking by r2d_6_60 (10 GHz, mean over the two codes):")
    piv = df[df.case.str.startswith(("ff_10", "case_"))].groupby("model")[["r2d_6_60", "r2d_all"]].mean()
    print(piv.sort_values("r2d_6_60", ascending=False).round(3).to_string())
    print("\nsamples: theta 6-60 = %d, 0-90 = %d (1 deg grid)"
          % (df[df.case == "ff_10"].n_6_60.iloc[0], df[df.case == "ff_10"].n_all.iloc[0]))


if __name__ == "__main__":
    main()
