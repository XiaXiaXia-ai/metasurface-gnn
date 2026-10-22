# -*- coding: utf-8 -*-
"""Single-sample prediction: trained weights -> complex far field -> pattern file.

    python -m msgnn.predict --run runs/m3_s0 --case 0 --out runs/m3_s0/pred_0000.npz

The npz contains theta, phi, the complex E_theta / E_phi of the model, the total
sigma in dBsm, the measured pattern and the per-node complex weights q (so a
diagnosis can compare the learned correction with q0 and with the common mode b
of theory/REPORT.md).
"""
import argparse
import json
import os

import numpy as np
import torch

from .config import load_config
from .data.build_graph import collate
from .data.dataset import load_splits
from .data.normalizer import Normalizer
from .experiment import build_context, build_model, cast_batch


def predict_one(run_dir: str, case_idx: int, split: str = "test") -> dict:
    cfg = load_config(os.path.join(run_dir, "config.yaml"))
    npath = os.path.join(run_dir, "normalizer.json")
    norm = Normalizer.load(npath) if os.path.isfile(npath) else None
    spath = os.path.join(run_dir, "splits.json")
    splits = load_splits(spath) if os.path.isfile(spath) else None
    ctx = build_context(cfg, out_dir=run_dir, norm=norm, splits=splits,
                        save=False, verbose=False)
    ds = ctx.ds[split]
    if case_idx not in ds.by_idx:
        raise KeyError("case %d is not in split %s (%d cases)"
                       % (case_idx, split, len(ds)))
    i = ds.index_of(case_idx)
    model = build_model(ctx)
    if cfg.model.name == "m1":
        raise ValueError("predict.py returns the complex far field; M1 only "
                         "predicts sigma_dB, use evaluate.py for it")
    ck = torch.load(os.path.join(run_dir, "best.pt"), map_location="cpu")
    model.load_state_dict(ck["model"])
    model.eval()
    batch = cast_batch(collate(ds.select([i])), ctx.dtype, ctx.device)
    with torch.no_grad():
        out = model(batch, return_fields=True)
    grid = ctx.grid
    eth = out["eth_re"][0].cpu().numpy() + 1j * out["eth_im"][0].cpu().numpy()
    eph = out["eph_re"][0].cpu().numpy() + 1j * out["eph_im"][0].cpu().numpy()
    sig_db = out["sig_db"][0].cpu().numpy()
    q = (out["q_re"][0].cpu().numpy() + 1j * out["q_im"][0].cpu().numpy())
    targ_db = ds.target_db[i].numpy()
    return {"theta": grid.theta, "phi": grid.phi, "eth": eth, "eph": eph,
            "sig_db": sig_db, "target_db": targ_db, "q": q,
            "q0": batch["q0"][0].cpu().numpy(),
            "case": ds.cases[i], "cfg": cfg}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="predict one sample")
    ap.add_argument("--run", required=True)
    ap.add_argument("--case", type=int, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    r = predict_one(args.run, args.case, args.split)
    out = args.out or os.path.join(args.run, "pred_%04d.npz" % args.case)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    np.savez(out, theta=r["theta"], phi=r["phi"], eth=r["eth"], eph=r["eph"],
             sig_db=r["sig_db"], target_db=r["target_db"], q=r["q"], q0=r["q0"])
    i0 = int(np.argmin(np.abs(r["theta"])))
    print("case %d (%s) -> %s" % (args.case, r["case"].name, out))
    print("  specular: model %.2f dBsm | measured %.2f dBsm"
          % (r["sig_db"][i0], r["target_db"][i0]))
    band = r["theta"] >= 10.0
    print("  mean far: model %.2f dBsm | measured %.2f dBsm"
          % (10 * np.log10((10 ** (r["sig_db"][band] / 10)).mean()),
             10 * np.log10((10 ** (r["target_db"][band] / 10)).mean())))
    dq = r["q"] - r["q0"]
    print("  q: |q0| mean %.3f | |dq| mean %.3f | mean(dq) %.4f%+.4fj"
          % (np.abs(r["q0"]).mean(), np.abs(dq).mean(),
             dq.real.mean(), dq.imag.mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
