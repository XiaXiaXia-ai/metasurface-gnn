# -*- coding: utf-8 -*-
"""Evaluation: the fixed metric triple + bands + per-sample error distribution.

The metrics are the ones the attribution report settled on
(theory/REPORT.md sec. 4.6), because a single correlation coefficient picks the
wrong model here: the specular lobe is 25-30 dB above the diffuse floor and owns
the variance.

    rho_lin     Pearson r of the LINEAR power sigma over theta in [0, 90]
                (this is the 'did you fill the 13.8 dB specular gap' metric)
    rho_db      Pearson r of sigma_dB over theta in [6, 90], measurement above
                -30 dBsm (this is the 'is the diffuse structure right' metric)
    bias_db     mean(sigma_hat_dB - sigma_dB) on the same set  (absolute level)
    rmse_db     RMS of the same residual
    + the five bands 0-5 / 5-15 / 15-30 / 30-60 / 60-90 deg, and the two scalar
      anchors specular_dbsm (theta = 0) and mean_far_dbsm (linear mean 10-90).

Usage
    python -m msgnn.evaluate --runs m0 m0g runs/m3_s0 --splits val,test --out runs
    python -m msgnn.evaluate --runs runs/m2_s0 runs/m3_s0 --out runs/cmp
"""
import argparse
import csv
import dataclasses
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from .config import Config, load_config
from .data.build_graph import collate
from .data.dataset import Grid, load_splits
from .data.normalizer import Normalizer
from .experiment import build_context, build_model, cast_batch
from .inference import predict_dataset
from .losses import angle_weights
from .physics import baseline as BL
from .physics import radiation as R

BAND_NAMES = ("b0_0_5", "b1_5_15", "b2_15_30", "b3_30_60", "b4_60_90")


# ------------------------------------------------------------------- metrics
def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3:
        return float("nan")
    if a.std() < 1e-12 or b.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def metrics_for_sample(pred_db: np.ndarray, targ_db: np.ndarray, grid: Grid,
                       ecfg) -> Dict[str, float]:
    """All metrics for one sample (pred/targ are flat dBsm patterns on the grid)."""
    p = np.maximum(np.asarray(pred_db, dtype=np.float64).ravel(), ecfg.db_floor)
    t = np.maximum(np.asarray(targ_db, dtype=np.float64).ravel(), ecfg.db_floor)
    th = grid.theta
    lin_p, lin_t = 10.0 ** (p / 10.0), 10.0 ** (t / 10.0)

    i0 = int(np.argmin(np.abs(th)))
    out = {"spec_pred": float(p[i0]), "spec_true": float(t[i0]),
           "spec_err": float(p[i0] - t[i0])}
    band_far = (th >= 10.0) & (th <= 90.0)
    mf_p = 10.0 * np.log10(max(lin_p[band_far].mean(), 1e-300))
    mf_t = 10.0 * np.log10(max(lin_t[band_far].mean(), 1e-300))
    out.update({"mean_far_pred": float(mf_p), "mean_far_true": float(mf_t),
                "mean_far_err": float(mf_p - mf_t)})

    front = th <= 90.0
    out["rho_lin"] = _pearson(lin_p[front], lin_t[front])

    lo, hi = float(ecfg.rho_band[0]), float(ecfg.rho_band[1])
    m = (th >= lo) & (th <= hi) & (t >= ecfg.meas_floor_db)
    out["n_pts"] = int(m.sum())
    out["rho_db"] = _pearson(p[m], t[m])
    d = p[m] - t[m]
    out["bias_db"] = float(d.mean()) if d.size else float("nan")
    out["rmse_db"] = float(np.sqrt(np.mean(d * d))) if d.size else float("nan")
    m2 = (th >= 6.0) & (th <= 90.0)
    out["rho_lin_6_90"] = _pearson(lin_p[m2], lin_t[m2])

    for name, (blo, bhi) in zip(BAND_NAMES, ecfg.bands):
        mb = (th >= blo) & ((th <= bhi) if name == BAND_NAMES[-1] else (th < bhi))
        mb = mb & (t >= ecfg.meas_floor_db)
        out["rho_" + name] = _pearson(p[mb], t[mb])
        dd = p[mb] - t[mb]
        out["bias_" + name] = float(dd.mean()) if dd.size else float("nan")
        out["rmse_" + name] = float(np.sqrt(np.mean(dd * dd))) if dd.size else float("nan")
        out["n_" + name] = int(mb.sum())
    return out


def summarize_rows(rows: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not rows:
        return {}
    keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float))
            and k not in ("case_idx",)]
    out = {}
    for k in keys:
        v = np.array([r.get(k, np.nan) for r in rows], dtype=float)
        v = v[np.isfinite(v)]
        out[k] = float(v.mean()) if v.size else float("nan")
    out["n_rows"] = len(rows)
    return out


# --------------------------------------------------------------- predictions
def _solid_weights_for_oracle(cfg: Config, grid: Grid) -> np.ndarray:
    """Per-angle weights of the oracle fit (main lobe boosted 10x, because a
    single complex scalar mainly has to explain the specular lobe)."""
    lc = dataclasses.replace(cfg.loss, angle_weight="solid_angle",
                             weight_floor=0.5, mainlobe_deg=6.0,
                             mainlobe_boost=10.0)
    return np.repeat(angle_weights(grid.theta_ax, lc), grid.n_phi)


def predict_baseline(ctx, split: str, oracle: bool = False) -> Dict[str, np.ndarray]:
    """M0 (oracle = M0 + one fitted complex scalar per sample)."""
    ds = ctx.ds[split]
    cfg = ctx.cfg
    grid = ctx.grid
    pos = R.lattice_positions(cfg.physics.n_side, cfg.physics.period_mm)
    w = _solid_weights_for_oracle(cfg, grid) if oracle else None
    preds, targ = [], []
    for i, c in enumerate(ds.cases):
        g0, gu = BL.field_terms(c.bits, grid.theta, grid.phi, ctx.library,
                                cfg.physics.freq_ghz, cfg.physics.period_mm,
                                cfg.physics.projection, pos)
        tdb = ds.target_db[i].numpy()
        if oracle:
            b, pdb, _ = BL.fit_global_scalar(g0, gu, tdb, w=w)
            preds.append(pdb)
        else:
            preds.append(10.0 * np.log10(np.maximum(np.abs(g0) ** 2, 1e-300)))
        targ.append(tdb)
    return {"pred_db": np.stack(preds, 0), "targ_db": np.stack(targ, 0),
            "case_idx": np.array([c.idx for c in ds.cases], dtype=np.int64),
            "names": [c.name for c in ds.cases]}


def predict_run(run_dir: str, split: str) -> Tuple[Config, Dict[str, np.ndarray], dict]:
    cfg = load_config(os.path.join(run_dir, "config.yaml"))
    npath = os.path.join(run_dir, "normalizer.json")
    norm = Normalizer.load(npath) if os.path.isfile(npath) else None
    spath = os.path.join(run_dir, "splits.json")
    splits = load_splits(spath) if os.path.isfile(spath) else None
    ctx = build_context(cfg, out_dir=run_dir, norm=norm, splits=splits,
                        save=False, verbose=False)
    model = build_model(ctx)
    ck = torch.load(os.path.join(run_dir, "best.pt"), map_location="cpu")
    model.load_state_dict(ck["model"])
    model.eval()
    res = predict_dataset(model, ctx.ds[split], batch_size=cfg.optim.batch_size,
                          device=ctx.device, dtype=ctx.dtype)
    return cfg, res, ck.get("meta", {})


# ------------------------------------------------------------------- driver
def run_eval(specs: Sequence[str], out_dir: str, splits: Sequence[str] = ("val", "test"),
             cfg_path: Optional[str] = None, verbose: bool = True,
             snapshot_path: Optional[str] = None,
             splits_path: Optional[str] = None) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ref = None
    for s in specs:
        if os.path.isdir(s) and os.path.isfile(os.path.join(s, "config.yaml")):
            c = load_config(os.path.join(s, "config.yaml"))
            sp = os.path.join(s, "splits.json")
            ref = build_context(c, out_dir=s,
                                splits=(load_splits(sp) if os.path.isfile(sp) else None),
                                save=False, verbose=False)
            break
    if ref is None:
        c = load_config(cfg_path) if cfg_path else load_config(None)
        sp = None
        if splits_path and os.path.isfile(splits_path):
            sp = load_splits(splits_path)
        ref = build_context(c, out_dir=out_dir, splits=sp, save=True,
                            verbose=verbose, snapshot_path=snapshot_path)

    rows: List[dict] = []
    for spec in specs:
        if spec in ("m0", "m0g"):
            name = "M0" if spec == "m0" else "M0g_oracle"
            meta = {"seed": 0, "n_params": 0}
            for split in splits:
                res = predict_baseline(ref, split, oracle=(spec == "m0g"))
                rows += _rows(name, split, res, ref.grid, ref.cfg, meta)
            if verbose:
                print("[eval] %s done" % name)
            continue
        run_dir = spec
        run_name = os.path.basename(os.path.normpath(run_dir))
        grid_run = _grid_of(run_dir)
        for split in splits:
            cfg, res, meta = predict_run(run_dir, split)
            nm = "%s(%s)" % (cfg.model.name.upper(), run_name)
            rows += _rows(nm, split, res, grid_run, cfg, meta)
        if verbose:
            print("[eval] %s done (%s)" % (run_name, meta.get("model")))
    path = os.path.join(out_dir, "metrics.csv")
    keys = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # summary
    groups: Dict[Tuple[str, str], List[dict]] = {}
    for r in rows:
        groups.setdefault((r["model"], r["split"]), []).append(r)
    spath = os.path.join(out_dir, "metrics_summary.csv")
    summ_rows = []
    for (m, sp), rs in groups.items():
        s = summarize_rows(rs)
        s["model"] = m
        s["split"] = sp
        s["n_params"] = rs[0].get("n_params", "")
        s["seed"] = rs[0].get("seed", "")
        summ_rows.append(s)
    if summ_rows:
        cols = ["model", "split", "seed", "n_params"] + [
            k for k in summ_rows[0] if k not in ("model", "split", "seed", "n_params")]
        with open(spath, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in summ_rows:
                w.writerow(r)
    if verbose and summ_rows:
        _print_table(summ_rows)
    return {"metrics": path, "summary": spath}


def _grid_of(run_dir: str) -> Grid:
    p = os.path.join(run_dir, "snapshot.json")
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as fh:
            snap = json.load(fh)
        return Grid.from_step(float(snap.get("grid", {}).get("step", 2.0)))
    return Grid.from_step(2.0)


def _rows(name: str, split: str, res: dict, grid: Grid, cfg: Config, meta: dict) -> List[dict]:
    out = []
    n = len(res["pred_db"])
    for i in range(n):
        r = metrics_for_sample(res["pred_db"][i], res["targ_db"][i], grid, cfg.eval)
        r.update({"model": name, "split": split,
                  "case_idx": int(res["case_idx"][i]),
                  "name": res["names"][i],
                  "seed": int(meta.get("seed", 0)),
                  "n_params": int(meta.get("n_params", 0))})
        out.append(r)
    return out


def _print_table(rows: Sequence[dict]) -> None:
    hdr = ("model", "split", "rho_lin", "rho_db", "bias_db", "rmse_db",
           "spec_err", "mean_far_err")
    print("%-28s %-5s %8s %8s %8s %8s %8s %8s" % hdr)
    for r in rows:
        print("%-28s %-5s %8.3f %8.3f %+8.2f %8.2f %+8.2f %+8.2f"
              % (r["model"], r["split"], r.get("rho_lin", np.nan),
                 r.get("rho_db", np.nan), r.get("bias_db", np.nan),
                 r.get("rmse_db", np.nan), r.get("spec_err", np.nan),
                 r.get("mean_far_err", np.nan)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="evaluate models with the fixed metric triple")
    ap.add_argument("--runs", nargs="+", required=True,
                    help="run directories and/or the literals m0 / m0g")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--splits", default="val,test")
    ap.add_argument("--config", default=None, help="config for the m0-only case")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--splits-file", default=None)
    args = ap.parse_args(argv)
    run_eval(args.runs, args.out,
             splits=[s.strip() for s in args.splits.split(",") if s.strip()],
             cfg_path=args.config, snapshot_path=args.snapshot,
             splits_path=args.splits_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
