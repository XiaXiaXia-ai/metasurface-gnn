# -*- coding: utf-8 -*-
"""compare.py -- one command: every theoretical model x every measured case.

    python compare.py            # results.csv, results.md, figs/*.png, nearfield.csv
    python compare.py --quick    # skip the slow angular-spectrum cases

Fitting protocol (important for reading the table honestly)
----------------------------------------------------------
All free parameters are fitted ONCE on the 10 GHz baseline case (ff_10, 1 deg grid,
baseline code) and then frozen for the other four frequencies and for the second
random code.  Nothing is re-fitted per case.  Each parameter is fitted to the one
observable the model is designed to explain:

    M1   (a0, a1)  linear LS on the dB pattern, theta 6..60 deg   (element pattern)
    M1b  a0        same, no shape parameter
    M2   |Gamma_gap|  root-find on the specular level             (H2 background)
    M6   c_couple     root-find on the specular level             (H1 coupling)

and everything else (diffuse mean, pattern correlation, RMSE, other frequencies,
other code) is then a *prediction*.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd
from scipy.optimize import brentq, least_squares

import common as C
import models as M

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")
os.makedirs(FIG, exist_ok=True)


# ------------------------------------------------------------------ case table
def build_cases():
    cases = []
    for f in C.FREQS:
        g, eth, eph = C.load_ff6(C.DATA_1DEG % f)
        cases.append(dict(name="ff_%s" % f, f=float(f), code="base", grid=g,
                          meas=C.total_db(eth, eph)))
    for idx, tag in ((0, "base"), (1, "c1")):
        g, eth, eph = C.load_ff4(C.DATA_2DEG % idx)
        cases.append(dict(name="case_%04d" % idx, f=10.0, code=tag, grid=g,
                          meas=C.total_db(eth, eph)))
    return cases


def code_of(tag):
    return C.base_code_map()[0] if tag == "base" else C.code_0001_map()[0]


# ---------------------------------------------------------------- model registry
FIT = {}
REPORT = {}


def af0(grid, f, cm, **kw):
    return M.af_ideal(grid, f, cm, **kw)


def build_models():
    """[(label, callable(grid, f, code_map) -> Field)] using the frozen FIT dict."""
    q, s1 = FIT["q"], FIT["s1"]
    s1b = FIT["s1b"]
    ggap = FIT["gamma_gap"]
    cpl = FIT["cpl"]
    W10 = M.coupling_matrix(10.0)
    return [
        ("M0_AF", lambda g, f, cm: M.af_ideal(g, f, cm)),
        ("M0b_AF_vector", lambda g, f, cm: M.af_ideal(g, f, cm, projection="vector")),
        ("M1_AF+element", lambda g, f, cm: M.af_element(g, f, cm, q=q, scale=s1)),
        ("M1b_AF+airy", lambda g, f, cm: M.af_element_airy(g, f, cm, scale=s1b)),
        ("M2_PO_fitted", lambda g, f, cm: M.po_two_region(g, f, cm, gamma_gap=ggap)),
        ("M2n_PO_nominal", lambda g, f, cm: M.po_two_region(g, f, cm)),
        ("M3_RS", lambda g, f, cm: M.rs_farfield(g, f, cm)),
        ("M4_AS_paper", lambda g, f, cm: M.as_farfield(g, f, cm, obliquity="paper")),
        ("M4c_AS_cos", lambda g, f, cm: M.as_farfield(g, f, cm, obliquity="cos")),
        ("M6_phase_compress", lambda g, f, cm: M.phase_compress(g, f, cm, alpha=FIT["alpha"],
                                                             gamma_abs=FIT["gabs"])),
        ("M6b_DDA_coupled", lambda g, f, cm: M.coupled_dipole(g, f, cm, cpl=cpl,
                                                             W=W10 if abs(f - 10.0) < 1e-9 else None)),
    ]


# ------------------------------------------------------------------- the fitting
def fit_all(cases):
    base = [c for c in cases if c["name"] == "ff_10"][0]
    g, f, cm, meas = base["grid"], base["f"], code_of(base["code"]), base["meas"]
    m0 = M.af_ideal(g, f, cm)
    d0 = m0.db
    sel = (g.th >= 6) & (g.th <= 60) & (meas > -30)

    # M1: model_dB = M0_dB + a0 + a1 * 20log10(cos th)   (linear in a0, a1)
    L = 20 * np.log10(np.maximum(np.cos(g.t), 1e-6))
    A = np.column_stack([np.ones(sel.sum()), L[sel]])
    a0, a1 = np.linalg.lstsq(A, (meas - d0)[sel], rcond=None)[0]
    FIT["q"] = float(a1)
    FIT["s1"] = float(10 ** (a0 / 20.0))

    # M1b: only a global scale on the analytic Airy element factor
    from scipy import special as sp
    qq = 2 * np.pi / C.lam_mm(f) * 4.7 * np.sin(g.t)
    airy_db = 20 * np.log10(np.abs(np.where(qq < 1e-9, 1.0, 2 * sp.j1(qq) / np.where(qq < 1e-9, 1.0, qq))))
    FIT["s1b"] = float(10 ** (np.mean((meas - d0)[sel] - airy_db[sel]) / 20.0))

    # M2: |Gamma_gap| that reproduces the measured specular (angle fixed at 142 deg)
    psi = np.radians(142.0)
    target = meas[0]

    def m2_res(gmag):
        return M.po_two_region(g, f, cm, gamma_gap=gmag * np.exp(1j * psi)).db[0] - target

    xs = np.linspace(0.0, 0.98, 40)
    ys = np.array([m2_res(x) for x in xs])
    FIT["gmag"] = float(brentq(m2_res, 0.0, 0.6)) if ys[0] * ys[np.argmax(xs > 0.6)] < 0 else float(xs[np.argmin(abs(ys))])
    FIT["gamma_gap"] = FIT["gmag"] * np.exp(1j * psi)

    # M6: complex coupling constant fitted to (specular, diffuse mean) jointly
    W = M.coupling_matrix(f)
    tgt = np.array([target, C.band_mean_db(g, meas, 10, 90)])

    def m6_res(x):
        cc = x[0] + 1j * x[1]
        fld = M.coupled_dipole(g, f, cm, cpl=cc, W=W)
        return np.array([fld.db[0] - tgt[0], C.band_mean_db(g, fld.db, 10, 90) - tgt[1]])

    best = None
    for x0 in ([0.0, 0.0], [-0.3, 0.3], [-0.6, 0.2], [0.1, 0.1]):
        r = least_squares(m6_res, x0, xtol=1e-8, ftol=1e-10, max_nfev=150)
        if best is None or r.cost < best.cost:
            best = r
    FIT["cpl"] = complex(best.x[0], best.x[1])

    # M6: phase-compression alpha and |Gamma| fitted to (specular, diffuse mean)
    def m6a_res(x):
        alpha, gabs = x
        fld = M.phase_compress(g, f, cm, alpha=alpha, gamma_abs=gabs)
        return np.array([fld.db[0] - tgt[0], C.band_mean_db(g, fld.db, 10, 90) - tgt[1]])

    r = least_squares(m6a_res, [0.8, 1.0], xtol=1e-10, ftol=1e-12, max_nfev=200)
    FIT["alpha"], FIT["gabs"] = float(r.x[0]), float(r.x[1])

    REPORT["fit"] = dict(q=round(float(FIT["q"]), 3), scale=round(float(FIT["s1"]), 3),
                         scale_airy=round(float(FIT["s1b"]), 3),
                         gamma_gap_abs=round(float(FIT["gmag"]), 3),
                         gamma_gap_deg=142.0,
                         cpl="%.3f%+.3fj" % (FIT["cpl"].real, FIT["cpl"].imag),
                         alpha=round(FIT["alpha"], 4), gamma_abs=round(FIT["gabs"], 4),
                         eff_phase_gap_deg=round(180.0 * FIT["alpha"], 2),
                         target_specular=round(float(target), 3))
    return FIT


# ------------------------------------------------------------------- the campaign
def run(models, cases, verbose=True):
    rows = []
    for label, fn in models:
        for c in cases:
            t0 = time.perf_counter()
            fld = fn(c["grid"], c["f"], code_of(c["code"]))
            dt = time.perf_counter() - t0
            m = C.metrics(c["grid"], c["meas"], fld.db)
            rows.append(dict(model=label, case=c["name"], **m, runtime_s=round(dt, 3)))
            if verbose:
                print("  %-16s %-9s  spec %7.2f  mean %7.2f  corr %.2f/%.2f/%.2f  rmse %5.2f  (%.2fs)"
                      % (label, c["name"], m["specular_dbsm"], m["mean_far_dbsm"],
                         m["corr_phi0"], m["corr_phi45"], m["corr_phi90"],
                         m["rmse_6_60deg"], dt))
    # measured reference rows (corr = 1, rmse = 0 by construction)
    for c in cases:
        m = C.metrics(c["grid"], c["meas"], c["meas"])
        rows.append(dict(model="MEASURED", case=c["name"], **m, runtime_s=0.0))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------- figures
def _uv_mesh(grid):
    n, p = grid.nth, grid.nph
    return grid.u.reshape(n, p), grid.v.reshape(n, p)


def uv_image(ax, grid, Zdb, vmin, vmax, cmap):
    """Interpolate the (theta, phi) pattern onto a Cartesian (u, v) grid and draw it."""
    from scipy.interpolate import griddata
    n = 321
    ax_ = np.linspace(-1, 1, n)
    UU, VV = np.meshgrid(ax_, ax_)
    Z = griddata((grid.u, grid.v), Zdb, (UU, VV), method="linear")
    Z = np.ma.masked_where((UU ** 2 + VV ** 2 > 1.0) | ~np.isfinite(Z), Z)
    return ax.imshow(np.clip(Z, vmin, vmax), origin="lower", extent=[-1, 1, -1, 1],
                     cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")


def fig_model(label, fld, case, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g, meas = case["grid"], case["meas"]
    U, V = _uv_mesh(g)
    Zm = fld.db.reshape(g.nth, g.nph)
    Zd = meas.reshape(g.nth, g.nph)
    vmax = max(Zm.max(), Zd.max())
    vmin = vmax - 35.0

    fig = plt.figure(figsize=(12.5, 6.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1.0], hspace=0.35, wspace=0.28)
    for k, (Z, ttl) in enumerate([(Zm, "model"), (Zd, "CST"), (Zm - Zd, "model - CST")]):
        ax = fig.add_subplot(gs[0, k])
        if k < 2:
            pc = uv_image(ax, g, np.asarray(Z).ravel(), vmin, vmax, "turbo")
        else:
            pc = uv_image(ax, g, np.asarray(Z).ravel(), -25, 25, "RdBu_r")
        ax.set_aspect("equal")
        ax.set_xlabel("u = sin$\\theta$cos$\\phi$")
        ax.set_ylabel("v = sin$\\theta$sin$\\phi$")
        ax.set_title(ttl, fontsize=10)
        fig.colorbar(pc, ax=ax, fraction=0.046, pad=0.03, label="dBsm")

    for k, pc in enumerate((0, 45, 90)):
        ax = fig.add_subplot(gs[1, k])
        m = g.cut(pc)
        ax.plot(g.th[m], meas[m], "k.", ms=2.0, label="CST")
        ax.plot(g.th[m], fld.db[m], "r-", lw=1.1, label="model")
        ax.set_xlim(0, 70)
        ax.set_ylim(max(-45, fld.db[m].max() - 45), fld.db[m].max() + 3)
        ax.set_xlabel("$\\theta$ (deg)")
        ax.set_ylabel("total $\\sigma$ (dBsm)")
        ax.set_title("$\\phi$ = %d deg" % pc, fontsize=10)
        ax.grid(alpha=0.3)
        if k == 0:
            ax.legend(fontsize=8, loc="upper right")

    mt = C.metrics(g, meas, fld.db)
    fig.suptitle("%s | %s | spec %.2f dBsm (CST %.2f)  mean %.2f (CST %.2f)  "
                 "corr %.2f/%.2f/%.2f  RMSE %.2f dB"
                 % (label, case["name"], mt["specular_dbsm"], meas[0],
                    mt["mean_far_dbsm"], C.band_mean_db(g, meas, 10, 90),
                    mt["corr_phi0"], mt["corr_phi45"], mt["corr_phi90"], mt["rmse_6_60deg"]),
                 fontsize=10)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def fig_summary(df, cases, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    freqs = [float(f) for f in C.FREQS]
    names = ["ff_%s" % f for f in C.FREQS]
    meas = [df[(df.model == "MEASURED") & (df.case == n)]["specular_dbsm"].iloc[0] for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.4))
    ax = axes[0]
    ax.plot(freqs, meas, "ko-", lw=2.4, ms=7, label="CST")
    for lab in df.model.unique():
        if lab == "MEASURED":
            continue
        v = [df[(df.model == lab) & (df.case == n)]["specular_dbsm"].iloc[0] for n in names]
        ax.plot(freqs, v, "--", lw=1.0, label=lab)
    ax.axhline(C.plate_dbsm(10.0), color="0.6", lw=1, ls=":")
    ax.text(9.82, C.plate_dbsm(10.0) + 0.3, "PEC plate 19.34", fontsize=8, color="0.4")
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("specular $\\sigma$ (dBsm)")
    ax.grid(alpha=0.3)
    ax.set_title("(a) specular level: the 8.6 dB dispersion is the fingerprint")
    ax.legend(fontsize=6.2, ncol=2, loc="lower right")

    ax = axes[1]
    meas_m = [df[(df.model == "MEASURED") & (df.case == n)]["mean_far_dbsm"].iloc[0] for n in names]
    ax.plot(freqs, meas_m, "ko-", lw=2.4, ms=7, label="CST")
    for lab in df.model.unique():
        if lab == "MEASURED":
            continue
        v = [df[(df.model == lab) & (df.case == n)]["mean_far_dbsm"].iloc[0] for n in names]
        ax.plot(freqs, v, "--", lw=1.0, label=lab)
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("mean $\\sigma$, $\\theta$ = 10..90 deg (dBsm)")
    ax.grid(alpha=0.3)
    ax.set_title("(b) diffuse level: all models agree with CST to ~1 dB")
    ax.legend(fontsize=6.2, ncol=2, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------- near-field check
def nearfield(quick=False):
    """RS (LPR eq. 4, spatial sum) vs AS (FFT propagator) at 20 lambda / 30 lambda."""
    cm = code_of("base")
    g = C.grid_1deg()
    far = M.rs_farfield(g, 10.0, cm)
    th = np.arange(-20, 20.01, 0.5)
    rows = []
    fig_data = []
    for z in (600.0, 900.0):
        E_rs, _ = M.rs_nearfield_cut(10.0, cm, z, th, dx_mm=1.0, two_term=True)
        E_rs1, _ = M.rs_nearfield_cut(10.0, cm, z, th, dx_mm=1.0, two_term=False)
        x, fld = M.as_nearfield_map(10.0, cm, z, dx_mm=2.0, n_fft=2048)
        i0 = len(x) // 2
        xo = z * np.tan(np.radians(th))
        E_as = (np.interp(xo, x, fld.real[:, i0])
                + 1j * np.interp(xo, x, fld.imag[:, i0]))
        d = 20 * np.log10(np.abs(E_rs) / np.abs(E_as))
        core = np.abs(th) <= 10
        rows.append(dict(z_mm=z, z_over_lambda=z / C.lam_mm(10.0),
                         max_dev_core_db=float(np.max(np.abs(d[core]))),
                         rms_dev_core_db=float(np.sqrt(np.mean(d[core] ** 2))),
                         max_dev_two_term_db=float(np.max(np.abs(
                             20 * np.log10(np.abs(E_rs) / np.abs(E_rs1) + 1e-30)))),
                         onaxis_rs=float(np.abs(E_rs)[np.argmin(np.abs(th))]),
                         onaxis_as=float(np.abs(E_as)[np.argmin(np.abs(th))]),
                         farfield_amplitude=float(10 ** (far.db[0] / 20) / (2 * np.sqrt(np.pi)) / z)))
        fig_data.append((z, th, 20 * np.log10(np.abs(E_rs) + 1e-30),
                         20 * np.log10(np.abs(E_as) + 1e-30)))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for z, t, rs, as_ in fig_data:
        ax.plot(t, rs, "r-", lw=1.4, label="RS eq.(4)  z = %d mm (%.0f$\\lambda$)" % (z, z / C.lam_mm(10.0)))
        ax.plot(t, as_, "b--", lw=1.0, label="AS FFT     z = %d mm" % z)
    # far field mapped to the same abscissa for reference
    fi = np.interp(th, g.th, far.db)
    ax.plot(th, fi - 20 * np.log10(np.maximum(np.cos(np.radians(th)), 1e-3) * 0 + 1), "k:",
            lw=1.0, label="far field (unscaled)")
    ax.set_xlabel("$\\theta$ (deg) on the $\\phi$ = 0 cut")
    ax.set_ylabel("|E| (dB, same units)")
    ax.set_title("Rayleigh-Sommerfeld vs angular spectrum at 20$\\lambda$ / 30$\\lambda$")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "nearfield_rs_vs_as.png"), dpi=130)
    plt.close(fig)
    return pd.DataFrame(rows), far


# ------------------------------------------------------------------------- main
def main():
    t_start = time.perf_counter()
    print("[1/4] loading measured cases")
    cases = build_cases()
    for c in cases:
        print("   %-9s f=%.1f GHz  %s  %d samples  spec %.2f  mean %.2f"
              % (c["name"], c["f"], c["code"], len(c["grid"]), c["meas"][0],
                 C.band_mean_db(c["grid"], c["meas"], 10, 90)))

    print("[2/4] fitting free parameters on the 10 GHz baseline only")
    fit_all(cases)
    for k, v in REPORT["fit"].items():
        print("   %-18s %s" % (k, v))

    print("[3/4] evaluating models")
    models = build_models()
    df = run(models, cases)
    df.to_csv(os.path.join(HERE, "results.csv"), index=False,
              float_format="%.3f")
    print("   -> results.csv (%d rows)" % len(df))

    print("[4/4] figures")
    base = [c for c in cases if c["name"] == "ff_10"][0]
    for label, fn in models:
        fld = fn(base["grid"], base["f"], code_of(base["code"]))
        fig_model(label, fld, base, os.path.join(FIG, "model_%s.png" % label.replace("/", "_")))
        print("   figs/model_%s.png" % label)
    fig_summary(df, cases, os.path.join(FIG, "summary_specular_vs_freq.png"))

    nf, far = nearfield()
    nf.to_csv(os.path.join(HERE, "nearfield.csv"), index=False, float_format="%.4f")
    print("   near-field check:", nf.to_dict("records"))
    print("done in %.1f s" % (time.perf_counter() - t_start))


if __name__ == "__main__":
    main()
