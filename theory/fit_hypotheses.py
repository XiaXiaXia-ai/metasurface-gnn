# -*- coding: utf-8 -*-
"""fit_hypotheses.py -- quantitative attribution of the 13.8 dB specular gap.

Three candidate mechanisms are tested against the measured far field.

  H1  in-array phase compression.  Gamma_bit -> |Gamma| exp(j alpha phi_bit).
      The local-periodicity value (alpha = 1, 180 deg) is the null hypothesis;
      mutual coupling or a shifted working point gives alpha < 1.

  H2  unmodulated coherent background.  Gamma_bit -> Gamma_bit + B,
      B = beta exp(j psi_B).  The physical anchor for psi_B is the bare grounded
      slab, whose transmission-line reflection is 1.000 angle 141.9 deg at 10 GHz.

  H3  edge / ground-plane specular.  The 1.5 mm rim of the finite PEC ground
      plane, integrated with the physical-optics rim current.

The two families are compared at *equal information*: each has exactly one free
parameter and each is forced to reproduce the measured specular (10.798 dBsm), so
only the *shape* of the pattern decides between them.

Outputs: hypotheses.csv, hypotheses_valley.csv, dispersion.csv, achievable.csv,
cell_model.csv and five figures in figs/.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

import common as C
import models as M

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs")
os.makedirs(FIG, exist_ok=True)

G = C.grid_1deg()
CM, _ = C.base_code_map()
MEAS = C.total_db(*C.load_ff6(C.DATA_1DEG % "10")[1:])
TGT_SPEC = float(MEAS[0])
TGT_MEAN = C.band_mean_db(G, MEAS, 10, 90)
PHI0, PHI1 = C.GAMMA_PH_DEG
PHI_MID = 0.5 * (PHI0 + PHI1)
SPEC_AMP = 10 ** (TGT_SPEC / 20.0) / C.const_C(10.0)   # required |sum w|
BY_BIT = (np.asarray(CM).ravel() == 0)


# --------------------------------------------------------------------------- helpers
def evaluate(weights, f_ghz=10.0, grid=G, meas=MEAS):
    fld = M.af_ideal(grid, f_ghz, CM, weights=np.asarray(weights).reshape(C.N_SIDE, C.N_SIDE))
    mt = C.metrics(grid, meas, fld.db)
    return dict(spec=float(fld.db[0]), mean=C.band_mean_db(grid, fld.db, 10, 90),
                corr0=mt["corr_phi0"], corr45=mt["corr_phi45"], corr90=mt["corr_phi90"],
                rmse=mt["rmse_6_60deg"])


def pair_compress(dphi_deg):
    """Coding pair with phase difference dphi, symmetric about 0 (global rotation)."""
    ph = 0.5 * np.radians(dphi_deg)
    return np.where(BY_BIT, np.exp(-1j * ph), np.exp(1j * ph))


def h1_family(dphi_deg, gabs=None):
    """H1: pure phase compression, |Gamma| scaled so that the specular is matched."""
    w = pair_compress(dphi_deg)
    if gabs is None:
        gabs = SPEC_AMP / abs(np.sum(w))
    return gabs * w, gabs


GABS = None          # |Gamma| implied by the measured diffuse level (set in main)


def h2_family(psi_deg, beta=None, gabs=None):
    """H2: Floquet pair (scaled to |Gamma|) + uniform background B = beta exp(j psi)."""
    gg = GABS if gabs is None else gabs
    w = gg * np.exp(1j * np.radians(np.where(BY_BIT, PHI0, PHI1)))
    if beta is None:
        u = 400 * np.exp(1j * np.radians(psi_deg))
        s0 = np.sum(w)
        a2 = abs(u) ** 2
        b2 = 2 * np.real(s0 * np.conj(u))
        c2 = abs(s0) ** 2 - SPEC_AMP ** 2
        rts = np.roots([a2, b2, c2])
        cand = [x.real for x in rts if abs(x.imag) < 1e-9 and x.real > 0]
        beta = min(cand) if cand else float(np.sqrt(max(-c2 / a2, 0.0)))
    return w + beta * np.exp(1j * np.radians(psi_deg)), beta


# ------------------------------------------------------------------------ scans
def scan_h1():
    """H1 with |Gamma| pinned by the diffuse level: solve dphi on the specular."""
    rows = []
    for dphi in np.arange(110, 180.5, 2.5):
        w = GABS * pair_compress(dphi)
        rows.append(dict(dphi=float(dphi), gabs=GABS, **evaluate(w)))
    return pd.DataFrame(rows)


def scan_h2():
    rows = []
    for psi in np.arange(0, 360, 5.0):
        w, beta = h2_family(psi)
        rows.append(dict(psi=float(psi), beta=float(beta), **evaluate(w)))
    return pd.DataFrame(rows)


def valley():
    """Two-parameter family (dphi, |B|) with the physical background phase 142 deg."""
    rows = []
    for dphi in np.arange(60, 180.1, 10):
        alpha = dphi / C.GAMMA_DEG
        wc = GABS * np.exp(1j * np.radians(alpha * np.where(BY_BIT, PHI0, PHI1)))
        s0 = np.sum(wc)
        u = 400 * np.exp(1j * np.radians(141.9))
        a2, b2, c2 = abs(u) ** 2, 2 * np.real(s0 * np.conj(u)), abs(s0) ** 2 - SPEC_AMP ** 2
        rts = np.roots([a2, b2, c2])
        cand = [x.real for x in rts if abs(x.imag) < 1e-9 and x.real > 0]
        beta = min(cand) if cand else np.nan
        if not np.isfinite(beta):
            rows.append(dict(dphi=dphi, beta=np.nan, spec=np.nan, mean_far=np.nan,
                             corr0=np.nan, corr45=np.nan, corr90=np.nan, rmse=np.nan))
            continue
        r = evaluate(wc + beta * np.exp(1j * np.radians(141.9)))
        r2 = dict(r); r2["mean_far"] = r2.pop("mean"); rows.append(dict(dphi=dphi, beta=beta, **r2))
    return pd.DataFrame(rows)


# ------------------------------------------------------- H2g: geometric two-region PO
def h2_geometric():
    rows = []
    r_ = np.where(CM == 0, C.PATCH_R_MM[0], C.PATCH_R_MM[1])
    ap_ = np.pi * r_ ** 2
    wbit = np.where(CM == 0, C.GAMMA[0], C.GAMMA[1])
    for gmag in np.arange(0.2, 1.45, 0.05):
        for psi in np.arange(0, 360, 10):
            gg = gmag * np.exp(1j * np.radians(psi))
            w = wbit * ap_ / C.A_CELL_MM2 + gg * (1 - ap_ / C.A_CELL_MM2)
            fld = M.af_ideal(G, 10.0, CM, weights=w)
            rows.append(dict(gmag=gmag, psi=psi, spec=float(fld.db[0]),
                             mean_far=C.band_mean_db(G, fld.db, 10, 90)))
    df = pd.DataFrame(rows)
    df["joint"] = (df["spec"] - TGT_SPEC).abs() + (df["mean_far"] - TGT_MEAN).abs()
    b = df.loc[df["joint"].idxmin()].to_dict()
    fld = M.po_two_region(G, 10.0, CM)
    nom = dict(gmag=float(np.abs(M.slab_gamma(10.0))),
               psi=float(np.degrees(np.angle(M.slab_gamma(10.0)))),
               spec=float(fld.db[0]), mean=C.band_mean_db(G, fld.db, 10, 90))
    nom["joint"] = abs(nom["spec"] - TGT_SPEC) + abs(nom["mean"] - TGT_MEAN)
    return df, b, nom


# ------------------------------------------------------------ H3: rim of the ground plane
def h3_rim(theta_deg, phi_deg, half_mm=140.0, thick_mm=1.5, f_ghz=10.0):
    """Far field of the ground-plane rim (PO current J = 2 n x H_inc).

    Under x-polarised normal incidence only the rims whose normal is +/-x carry
    current (J = -/+ 2 E0/Z0 zhat); the +/-y rims have n x H = 0.  The two surviving
    rims are antiparallel z-currents separated by 280 mm, so

        sqrt(sigma_rim) = (2 sqrt(pi)/lambda) sin(theta) |2j sin(k 140 u) I_y I_z|

    which is *identically zero* on boresight: H3 cannot produce a broadside spike.
    """
    lam = C.lam_mm(f_ghz)
    k = 2 * np.pi / lam
    th = np.radians(np.asarray(theta_deg, dtype=float))
    ph = np.radians(np.asarray(phi_deg, dtype=float))
    u = np.sin(th) * np.cos(ph)
    v = np.sin(th) * np.sin(ph)
    w = np.cos(th)
    Iy = 2 * half_mm * np.sinc(k * half_mm * v / np.pi)
    Iz = thick_mm * np.exp(1j * k * thick_mm * w / 2) * np.sinc(k * thick_mm * w / (2 * np.pi))
    amp = np.abs(2j * np.sin(k * half_mm * u) * Iy * Iz) * np.sin(th)
    return 20 * np.log10(2 * np.sqrt(np.pi) / lam * 1e-3 * amp + 1e-30)


# ------------------------------------------------------------------ dispersion fit
def dispersion():
    freqs, a_abs, dphi = [], [], []
    for f in C.FREQS:
        ff = float(f)
        g, eth, eph = C.load_ff6(C.DATA_1DEG % f)
        tot = C.total_db(eth, eph)
        a = 10 ** ((tot[0] - C.plate_dbsm(ff)) / 20.0)
        freqs.append(ff)
        a_abs.append(a)
        dphi.append(2 * np.degrees(np.arccos(np.clip(a, -1, 1))))
    freqs, a_abs, dphi = map(np.asarray, (freqs, a_abs, dphi))

    def model(p):
        f0, Q = p
        return 180.0 - 2 * np.degrees(np.arctan(2 * Q * (freqs - f0) / f0))

    r = least_squares(lambda p: model(p) - dphi, [9.5, 4.0], xtol=1e-13, ftol=1e-13)
    f0, Q = r.x
    pred = model(r.x)
    plate = np.array([C.plate_dbsm(x) for x in freqs])
    spec_db = 20 * np.log10(a_abs) + plate
    pred_db = 20 * np.log10(np.abs(np.cos(np.radians(pred / 2))) + 1e-12) + plate
    return pd.DataFrame(dict(freq=freqs, a=a_abs, dphi=dphi, dphi_fit=pred,
                             spec_db=spec_db, spec_fit_db=pred_db)), float(f0), float(Q)


# ------------------------------------------------------------- achievable reduction
def achievable():
    rows = []
    w180 = np.where(BY_BIT, np.exp(1j * np.radians(PHI0)), np.exp(1j * np.radians(PHI1)))
    rows.append(("A current code, ideal 180 deg pair, no background", evaluate(w180)))
    psi = 141.9
    b = h2_family(psi)[1]
    rows.append(("B current code, 180 deg pair + background b=%.2f kept" % b,
                 evaluate(w180 + b * np.exp(1j * np.radians(psi)))))
    rng = np.random.default_rng(7)
    bits = np.array([1] * 50 + [0] * 50)
    rng.shuffle(bits)
    cmb = np.repeat(np.repeat(bits.reshape(10, 10), 2, 0), 2, 1)
    wb = np.where((cmb == 0).ravel(), np.exp(1j * np.radians(PHI0)),
                  np.exp(1j * np.radians(PHI1)))
    rows.append(("C balanced code, ideal 180 deg pair, no background", evaluate(wb)))
    rows.append(("D balanced code + background b=%.2f kept" % b,
                 evaluate(wb + b * np.exp(1j * np.radians(psi)))))
    vals = []
    for s in range(20):
        r = np.random.default_rng(100 + s)
        vals.append(evaluate(wb * np.exp(1j * np.radians(r.normal(0, 10.0, 400))))["spec"])
    rows.append(("E balanced code + 10 deg rms phase error (practical floor)",
                 dict(spec=float(np.mean(vals)), mean=np.nan, corr0=np.nan,
                      corr45=np.nan, corr90=np.nan, rmse=np.nan)))
    return pd.DataFrame([dict(case=k, specular=v["spec"], mean_far=v["mean"],
                              reduction_db=C.plate_dbsm(10.0) - v["spec"])
                         for k, v in rows])


# ------------------------------------------------------------------- cell model (M5)
def cell_model():
    rows = []
    for f in np.arange(9.6, 10.41, 0.1):
        Gs = M.slab_gamma(f)
        rows.append(dict(model="grounded slab TL", f_ghz=round(float(f), 2),
                         abs_gamma=abs(Gs), phase_deg=float(np.degrees(np.angle(Gs))),
                         db=20 * np.log10(abs(Gs))))
    for r in C.PATCH_R_MM:
        for fr in (1.0, 0.5, 0.2, 0.05):
            Gl = M.lc_element(10.0, r, fringing=fr)
            rows.append(dict(model="LC element fringing=%.2f" % fr, f_ghz=10.0,
                             abs_gamma=abs(Gl), phase_deg=float(np.degrees(np.angle(Gl))),
                             db=20 * np.log10(abs(Gl))))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------- main
def main():
    print("targets: specular %.3f dBsm | diffuse mean %.3f dBsm | plate %.3f dBsm"
          % (TGT_SPEC, TGT_MEAN, C.plate_dbsm(10.0)))

    global GABS
    # |Gamma| from the diffuse mean: it is the only quantity the diffuse level sees
    def mean_res(g):
        fld = M.af_ideal(G, 10.0, CM, gamma=tuple(g * np.exp(1j * np.radians(p))
                                                  for p in C.GAMMA_PH_DEG))
        return C.band_mean_db(G, fld.db, 10, 90) - TGT_MEAN
    GABS = float(least_squares(lambda x: [mean_res(x[0])], [0.9], xtol=1e-12).x[0])
    print("|Gamma| implied by the diffuse mean: %.4f  (Floquet value 0.867/0.852)"
          % GABS)
    print("\n[H1] pure phase-compression family (1 parameter, specular fixed)")
    h1 = scan_h1()
    print(h1.to_string(index=False, float_format=lambda v: "%9.3f" % v))
    print("\n[H2] background family (1 parameter, specular fixed)")
    h2 = scan_h2()
    print(h2.to_string(index=False, float_format=lambda v: "%9.3f" % v))

    i1 = h1.rmse.idxmin()
    i2 = h2.rmse.idxmin()
    ref1 = h1.iloc[(h1.dphi - 180).abs().idxmin()]
    ref2 = h2.iloc[(h2.psi - 141.9).abs().idxmin()]
    print("\nbest H1 member : dphi %.1f deg, |Gamma| %.3f -> corr %.2f/%.2f/%.2f  rmse %.2f  mean %.2f"
          % (h1.loc[i1, "dphi"], h1.loc[i1, "gabs"], h1.loc[i1, "corr0"], h1.loc[i1, "corr45"],
             h1.loc[i1, "corr90"], h1.loc[i1, "rmse"], h1.loc[i1, "mean"]))
    print("best H2 member : psi %.0f deg, beta %.3f -> corr %.2f/%.2f/%.2f  rmse %.2f  mean %.2f"
          % (h2.loc[i2, "psi"], h2.loc[i2, "beta"], h2.loc[i2, "corr0"], h2.loc[i2, "corr45"],
             h2.loc[i2, "corr90"], h2.loc[i2, "rmse"], h2.loc[i2, "mean"]))
    print("H2 at the physical slab phase (142 deg): beta %.3f -> corr %.2f/%.2f/%.2f  rmse %.2f"
          % (ref2["beta"], ref2["corr0"], ref2["corr45"], ref2["corr90"], ref2["rmse"]))

    print("\n[H1/H2] two-parameter valley with the physical background phase")
    dv = valley()
    print(dv.to_string(index=False, float_format=lambda v: "%9.3f" % v))

    print("\n[H2g] geometric two-region PO: scan (|Gamma_gap|, angle)")
    df2, best2, nom2 = h2_geometric()
    print("   nominal TL slab   |Ggap| %.3f ang %.1f -> spec %.2f  mean %.2f  joint %.2f"
          % (nom2["gmag"], nom2["psi"], nom2["spec"], nom2["mean"], nom2["joint"]))
    print("   best joint fit    |Ggap| %.2f ang %.0f -> spec %.2f  mean %.2f  joint %.2f"
          % (best2["gmag"], best2["psi"], best2["spec"], best2["mean_far"], best2["joint"]))

    print("\n[H3] rim of the ground plane")
    th = np.arange(0, 60, 0.5)
    rim = h3_rim(th, 0.0)
    print("   rim peak %.2f dBsm at theta %.1f deg; rim(theta=0) = %.1f dBsm"
          % (rim.max(), th[int(np.argmax(rim))], rim[0]))
    print("   measured specular %.2f dBsm -> rim peak is %.1f dB too weak"
          % (TGT_SPEC, TGT_SPEC - rim.max()))

    print("\n[dispersion] |a|(f) -> dphi(f) -> (f0, Q)")
    dfd, f0, Q = dispersion()
    print(dfd.to_string(index=False, float_format=lambda v: "%9.3f" % v))
    print("   f0 = %.3f GHz  Q = %.2f  (isolated-cell 180 deg crossing: 10.000 GHz)" % (f0, Q))

    print("\n[achievable] best specular for each repair")
    dfa = achievable()
    print(dfa.to_string(index=False, float_format=lambda v: "%9.2f" % v))

    print("\n[cell model] M5")
    dfc = cell_model()
    print(dfc.to_string(index=False, float_format=lambda v: "%9.4f" % v))

    # H1 with the specular matched by Delta-phi (|Gamma| pinned by the diffuse)
    jm = int(np.argmin(np.abs(h1["spec"].values - TGT_SPEC)))
    h1m = h1.iloc[jm]
    # H1 as a two-parameter fit to (specular, diffuse mean): alpha and |Gamma|
    def two_res(x):
        w = x[1] * np.exp(1j * np.radians(x[0] / C.GAMMA_DEG * np.where(BY_BIT, PHI0, PHI1)))
        r = evaluate(w)
        return [r["spec"] - TGT_SPEC, r["mean"] - TGT_MEAN]
    r2p = least_squares(two_res, [140.0, 1.05], bounds=([120.0, 0.90], [179.0, 1.30]),
                        xtol=1e-10, max_nfev=200)
    d2 = r2p.x[0] / C.GAMMA_DEG
    h1_2p = evaluate(r2p.x[1] * np.exp(
        1j * np.radians(d2 * np.where(BY_BIT, PHI0, PHI1))))

    rec = lambda v: dict(specular=v["spec"], mean_far=v["mean"], corr_phi0=v["corr0"],
                         corr_phi45=v["corr45"], corr_phi90=v["corr90"], rmse_6_60=v["rmse"])
    out = [
        dict(test="MEASURED (CST)", **{"specular": TGT_SPEC, "mean_far": TGT_MEAN,
                                       "corr_phi0": 1.0, "corr_phi45": 1.0, "corr_phi90": 1.0,
                                       "rmse_6_60": 0.0}),
        dict(test="H1 specular-matched (dphi=%.1f deg, |G|=%.3f)" % (h1m["dphi"], h1m["gabs"]),
             **rec(h1m)),
        dict(test="H1 2-param fit (dphi=%.1f deg, |G|=%.3f)" % (r2p.x[0], r2p.x[1]),
             **rec(h1_2p)),
        dict(test="H2 best (psi=%.0f deg, b=%.3f)" % (h2.loc[i2, "psi"], h2.loc[i2, "beta"]),
             **rec(h2.loc[i2])),
        dict(test="H2 physical (psi=142 deg, b=%.3f)" % ref2["beta"], **rec(ref2)),
        dict(test="H2g nominal PO (|Ggap|=1.000, 142 deg)",
             **{"specular": nom2["spec"], "mean_far": nom2["mean"], "corr_phi0": np.nan,
                "corr_phi45": np.nan, "corr_phi90": np.nan, "rmse_6_60": np.nan}),
        dict(test="H2g best PO fit (|Ggap|=%.2f, %.0f deg)" % (best2["gmag"], best2["psi"]),
             **{"specular": best2["spec"], "mean_far": best2["mean_far"], "corr_phi0": np.nan,
                "corr_phi45": np.nan, "corr_phi90": np.nan, "rmse_6_60": np.nan}),
        dict(test="H3 rim peak (280 x 1.5 mm)", **{"specular": float(rim.max()),
                                                   "mean_far": np.nan, "corr_phi0": np.nan,
                                                   "corr_phi45": np.nan, "corr_phi90": np.nan,
                                                   "rmse_6_60": np.nan}),
    ]
    pd.DataFrame(out).to_csv(os.path.join(HERE, "hypotheses.csv"), index=False,
                             float_format="%.3f")
    h1.to_csv(os.path.join(HERE, "hypotheses_h1.csv"), index=False, float_format="%.3f")
    h2.to_csv(os.path.join(HERE, "hypotheses_h2.csv"), index=False, float_format="%.3f")
    dv.to_csv(os.path.join(HERE, "hypotheses_valley.csv"), index=False, float_format="%.3f")
    df2.to_csv(os.path.join(HERE, "hypotheses_h2geo_scan.csv"), index=False, float_format="%.3f")
    dfd.to_csv(os.path.join(HERE, "dispersion.csv"), index=False, float_format="%.3f")
    dfa.to_csv(os.path.join(HERE, "achievable.csv"), index=False, float_format="%.3f")
    dfc.to_csv(os.path.join(HERE, "cell_model.csv"), index=False, float_format="%.4f")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    axes[0].plot(h1.dphi, h1.rmse, "o-", ms=3.5, label="H1 phase compression")
    axes[0].plot(h2.psi, h2.rmse, "s-", ms=3.0, label="H2 background")
    axes[0].axvline(180, color="0.6", ls=":", lw=1)
    axes[0].axvline(141.9, color="r", ls="--", lw=1)
    axes[0].set_xlabel("H1: $\\Delta\\varphi$ (deg)   /   H2: arg $B$ (deg)")
    axes[0].set_ylabel("dB RMSE, $\\theta$ = 6..60 deg")
    axes[0].set_title("(a) pattern residual at fixed specular")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    axes[1].plot(h1.dphi, h1.corr0, "o-", ms=3.0, label="H1 $\\phi$=0")
    axes[1].plot(h1.dphi, h1.corr45, "o--", ms=3.0, label="H1 $\\phi$=45")
    axes[1].plot(h2.psi, h2.corr0, "s-", ms=2.6, label="H2 $\\phi$=0")
    axes[1].plot(h2.psi, h2.corr45, "s--", ms=2.6, label="H2 $\\phi$=45")
    axes[1].axhline(0.83, color="0.5", ls=":", lw=1)
    axes[1].set_xlabel("H1: $\\Delta\\varphi$ (deg)   /   H2: arg $B$ (deg)")
    axes[1].set_ylabel("pattern correlation")
    axes[1].set_title("(b) speckle correlation; dotted = M0 (0.83)")
    axes[1].legend(fontsize=6.5, ncol=2)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hyp_h1_vs_h2.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot(dv.dphi, dv.beta, "o-")
    ax.set_xlabel("$\\Delta\\varphi$ (deg)")
    ax.set_ylabel("required background $|B|$ (PEC amplitude units)")
    ax.set_title("specular-matching valley: every $\\Delta\\varphi$ has a background that fits")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hyp_2dmap.png"), dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.0))
    axes[0].plot(dfd.freq, dfd.spec_db, "ko", ms=6, label="CST specular")
    axes[0].plot(dfd.freq, dfd.spec_fit_db, "r-", lw=1.3,
                 label="Lorentzian, $f_0$=%.2f GHz, Q=%.1f" % (f0, Q))
    axes[0].set_xlabel("frequency (GHz)")
    axes[0].set_ylabel("specular $\\sigma$ (dBsm)")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    axes[1].plot(dfd.freq, dfd.dphi, "ko-", label="inverted $\\Delta\\varphi_{eff}$")
    axes[1].plot(dfd.freq, dfd.dphi_fit, "r--", lw=1.3, label="Lorentzian fit")
    axes[1].axhline(180, color="0.6", ls=":", label="isolated cell (Floquet)")
    axes[1].set_xlabel("frequency (GHz)")
    axes[1].set_ylabel("$\\Delta\\varphi_{eff}$ (deg)")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hyp_dispersion.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(th, rim, "r-", lw=1.6, label="rim PO (280 x 1.5 mm)")
    ax.axhline(TGT_SPEC, color="k", ls="--", lw=1.2, label="CST specular 10.80 dBsm")
    ax.set_xlabel("$\\theta$ (deg), $\\phi$ = 0")
    ax.set_ylabel("$\\sigma$ (dBsm)")
    ax.set_ylim(-70, 15)
    ax.set_title("H3: rim has a null on boresight and peaks %.0f dB too low"
                 % (TGT_SPEC - rim.max()))
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hyp_h3_rim.png"), dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.0))
    fs = np.arange(9.6, 10.41, 0.02)
    axes[0].plot(fs, [np.degrees(np.angle(M.slab_gamma(f))) for f in fs], "b-", lw=1.6,
                 label="grounded slab TL")
    axes[0].set_xlabel("frequency (GHz)")
    axes[0].set_ylabel("arg $\\Gamma_{gap}$ (deg)")
    axes[0].set_title("bare substrate: |$\\Gamma$| = 0.9999, i.e. -0.0007 dB")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    rr = np.linspace(1.0, 6.0, 60)
    for fr, st in ((1.0, "-"), (0.2, "--"), (0.05, ":")):
        axes[1].plot(rr, [np.degrees(np.angle(M.lc_element(10.0, r, fringing=fr))) for r in rr],
                     st, lw=1.3, label="LC model, fringing %.2f" % fr)
    axes[1].plot([2.0, 4.7], [174.6, -5.3], "ko", ms=6, label="Floquet (CST)")
    axes[1].set_xlabel("patch radius r (mm)")
    axes[1].set_ylabel("arg $\\Gamma$ at 10 GHz (deg)")
    axes[1].set_title("unit-cell phase vs radius")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hyp_cell.png"), dpi=130)
    plt.close(fig)
    print("\nfigures written to figs/")


if __name__ == "__main__":
    main()
