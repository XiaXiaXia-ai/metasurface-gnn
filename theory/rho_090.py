# -*- coding: utf-8 -*-
"""rho_090.py -- standardised 0-90 deg Pearson comparison over many groups.

Metric standard (fixed here once and for all):

    window   theta in [0, 90) deg, i.e. the whole reflected wave; the single
             theta = 90 ring is excluded because the scalar aperture model gives
             cos(90) = 0 -> -300 dB there (a numerical degeneracy, not physics)
    floor    keep samples with CST > -30 dBsm
    domain   Pearson r of the dB values (primary), linear power (secondary)
    groups   E-plane (phi = 0), H-plane (phi = 90), and the full 2-D pattern
             (all phi at once), each on 7 measured cases:
             9.8 / 9.9 / 10 / 10.1 / 10.2 GHz + case_0000 (2 deg grid) +
             case_0001 (second random code)

Outputs
-------
rho_090_standard.csv   per model x case x metric
rho_090_summary.csv    grand mean / std per model, plus the metric-variant check
figs/rho090_rank.png   ranking with error bars + heat map over cases
figs/rho090_metrics.png  how much the ranking depends on the metric definition
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import common as C
import compare as CMP

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")
EDGE = 89.5


def rr(a, b, m):
    if m.sum() < 8:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])


def main():
    print("rebuilding model patterns ...")
    cases = CMP.build_cases()
    CMP.fit_all(cases)
    models = CMP.build_models()

    rows = []
    for lab, fn in models:
        for c in cases:
            g, meas = c["grid"], c["meas"]
            db = fn(g, c["f"], CMP.code_of(c["code"])).db
            base = (g.th < EDGE) & (meas > -30)
            mE = base & g.cut(0)
            mH = base & g.cut(90)
            lin = 10 ** (meas / 10.0)
            linm = 10 ** (db / 10.0)
            rows.append(dict(
                model=lab, case=c["name"],
                rE=rr(db, meas, mE), rH=rr(db, meas, mH),
                r2D=rr(db, meas, base),
                r2D_lin=rr(linm, lin, base),
                rEH_mean=0.5 * (rr(db, meas, mE) + rr(db, meas, mH)),
                r2D_6_90=rr(db, meas, base & (g.th >= 6.0)),
                rmse=float(np.sqrt(np.mean((db[base] - meas[base]) ** 2))),
                bias=float(np.mean(db[base] - meas[base])),
                rmse_shape=float(np.std(db[base] - meas[base]))))
            print("  %-18s %-9s  E %.3f  H %.3f  2D %.3f  (lin %.3f)  rmse %5.2f  bias %+5.2f"
                  % (lab, c["name"], rows[-1]["rE"], rows[-1]["rH"], rows[-1]["r2D"],
                     rows[-1]["r2D_lin"], rows[-1]["rmse"], rows[-1]["bias"]))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "rho_090_standard.csv"), index=False, float_format="%.3f")

    summ = df.groupby("model").agg(
        r2D=("r2D", "mean"), r2D_std=("r2D", "std"),
        rE=("rE", "mean"), rH=("rH", "mean"), rEH=("rEH_mean", "mean"),
        r2D_lin=("r2D_lin", "mean"), r2D_6_90=("r2D_6_90", "mean"),
        rmse=("rmse", "mean"), bias=("bias", "mean"),
        rmse_shape=("rmse_shape", "mean")).sort_values("r2D", ascending=False)
    summ["score"] = 0.5 * summ["r2D"] + 0.25 * summ["rE"] + 0.25 * summ["rH"]
    # gated criterion: shape matters, but a level error of more than ~3 dB disqualifies
    summ["gate"] = np.where(summ["bias"].abs() <= 3.0, "PASS", "fail")
    summ["score_gated"] = np.where(summ["bias"].abs() <= 3.0, summ["r2D"], np.nan)
    summ = summ.sort_values("score", ascending=False)
    summ.round(3).to_csv(os.path.join(HERE, "rho_090_summary.csv"),
                         float_format="%.3f")
    pd.set_option("display.width", 200)
    print("\n=== grand mean over the 7 cases, 0-90 deg window ===")
    print(summ.round(3).to_string())

    # how much does the ranking depend on the metric definition?
    base_rank = summ["score"].rank(ascending=False)
    print("\n=== rank agreement between metric variants (Spearman) ===")
    for col in ("rE", "rH", "rEH", "r2D_lin", "r2D", "r2D_6_90", "rmse", "rmse_shape"):
        rho_s = spearmanr(summ["score"], summ[col]).statistic
        print("  score vs %-8s  rho_s = %+.3f" % (col, rho_s))

    # ------------------------------------------------------------------ figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    COL = {"M0_AF": "#1f77b4", "M0b_AF_vector": "#5b9bd5", "M1_AF+element": "#2e7d32",
           "M1b_AF+airy": "#66bb6a", "M3_RS": "#6a1b9a", "M4_AS_paper": "#8e24aa",
           "M4c_AS_cos": "#ab47bc", "M2_PO_fitted": "#c62828", "M2n_PO_nominal": "#ef5350",
           "M6_phase_compress": "#795548", "M6b_DDA_coupled": "#a1887f"}
    order = summ.index.tolist()

    fig = plt.figure(figsize=(14.6, 6.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.30)
    ax = fig.add_subplot(gs[0, 0])
    y = np.arange(len(order))
    ax.barh(y, summ["r2D"].values, xerr=summ["r2D_std"].values,
            color=[COL[m] for m in order], alpha=0.9, capsize=2)
    for i, m in enumerate(order):
        ax.text(summ["r2D"].iloc[i] + 0.012, i, "%.3f" % summ["r2D"].iloc[i],
                va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.02)
    for i, m in enumerate(order):
        b = summ["bias"].iloc[i]
        ax.text(0.02, i, "bias %+.1f dB %s" % (b, "PASS" if abs(b) <= 3 else "fail"),
                va="center", fontsize=6.5, color="w" if summ["r2D"].iloc[i] < 0.6 else "k")
    ax.set_xlabel("2-D Pearson r, $\\theta$ = 0-90$^\\circ$, all $\\phi$  (mean $\\pm$ s.d. over 7 cases)")
    ax.set_title("(a) 0-90$^\\circ$ standard, with the level error printed", fontsize=10)
    ax.grid(axis="x", alpha=0.3)

    ax = fig.add_subplot(gs[0, 1])
    cases_order = [c["name"] for c in cases]
    Z = np.array([[df[(df.model == m) & (df.case == cs)]["r2D"].iloc[0] for cs in cases_order]
                  for m in order])
    im = ax.imshow(Z, cmap="RdYlGn", vmin=0.4, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(cases_order)))
    ax.set_xticklabels(cases_order, rotation=30, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    for i in range(Z.shape[0]):
        for j in range(Z.shape[1]):
            ax.text(j, i, "%.2f" % Z[i, j], ha="center", va="center", fontsize=7)
    ax.set_title("(b) per case (2-D, 0-90$^\\circ$)", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="Pearson r")
    fig.suptitle("Pearson correlation with the 0-90$^\\circ$ standard", fontsize=11)
    fig.savefig(os.path.join(FIG, "rho090_rank.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)

    # metric-variant comparison
    fig, ax = plt.subplots(figsize=(11.0, 4.6))
    variants = [("r2D", "2-D all $\\phi$ (dB)"), ("rE", "E-plane only"),
                ("rH", "H-plane only"), ("r2D_lin", "2-D, linear power")]
    w = 0.2
    for k, (col, lab) in enumerate(variants):
        ax.bar(np.arange(len(order)) + (k - 1.5) * w, summ.loc[order, col].values,
               width=w, label=lab, alpha=0.9)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0.3, 1.0)
    ax.set_ylabel("Pearson r (mean over 7 cases)")
    ax.set_title("how much the number depends on the metric definition (0-90$^\\circ$ window)",
                 fontsize=10)
    ax.legend(fontsize=8, ncol=4, loc="upper center")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "rho090_metrics.png"), dpi=140)
    plt.close(fig)
    print("\nwrote rho_090_standard.csv, rho_090_summary.csv, "
          "figs/rho090_rank.png, figs/rho090_metrics.png")


if __name__ == "__main__":
    main()
