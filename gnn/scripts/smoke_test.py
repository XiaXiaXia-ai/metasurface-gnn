# -*- coding: utf-8 -*-
"""End-to-end smoke test: 8 cases, 2 epochs, must finish well under 5 minutes.

    python scripts/smoke_test.py

Checks, in order
    1. the radiation operator reproduces the PEC plate (19.342 dBsm);
    2. the graph pipeline builds (nodes, edges, q0) and one forward/backward pass
       produces a finite loss and finite gradients;
    3. M3, M2 and M1 each train for 2 epochs on 8 cases;
    4. M0 (and the M0g oracle) evaluate on the smoke split and write metrics.csv;
    5. total wall time < 300 s.
Exit code 0 only if everything passed.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch

from msgnn.config import load_config
from msgnn.data.build_graph import collate
from msgnn.evaluate import run_eval
from msgnn.experiment import build_context, build_model, cast_batch
from msgnn.physics import radiation as R
from msgnn.train import train

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT_S = 300.0


def main() -> int:
    t0 = time.time()
    cfg_path = os.path.join(ROOT, "configs", "train_m3.yaml")
    cfg = load_config(cfg_path, overrides={"runtime": {"threads": 4, "log_every": 1}})
    work = os.path.join(ROOT, "runs", "smoke")
    os.makedirs(work, exist_ok=True)
    n_cases = 8
    n_epochs = 2
    ok = True

    # ---- 1. operator self-check
    plate = R.plate_dbsm()
    val = R.uniform_aperture_dbsm("vector")
    print("[1] uniform aperture -> %.4f dBsm (PEC plate %.4f, delta %+.2e)"
          % (val, plate, val - plate))
    ok &= abs(val - plate) < 1e-4

    # ---- 2. one forward/backward pass through the full pipeline
    cfg3 = load_config(cfg_path, overrides={"model": {"name": "m3"},
                                            "runtime": {"threads": 4}})
    ctx = build_context(cfg3, os.path.join(work, "ctx"), max_cases=n_cases,
                        verbose=True)
    model = build_model(ctx)
    batch = cast_batch(collate(ctx.ds["train"].select([0])), ctx.dtype)
    out = model(batch)
    loss = torch.mean((out["sig_db"] - batch["sig_db"]) ** 2)
    loss.backward()
    gnorm = float(sum(p.grad.abs().sum() for p in model.parameters()
                      if p.grad is not None))
    print("[2] forward/backward ok: loss %.3f  grad|.| %.3f  params %d"
          % (float(loss), gnorm, sum(p.numel() for p in model.parameters())))
    ok &= np.isfinite(float(loss)) and np.isfinite(gnorm) and gnorm > 0

    # ---- 3. two epochs per model
    runs = {}
    for name, cfg_file, extra in (
            ("m3", "train_m3.yaml", {}),
            ("m2", "train_m2.yaml", {}),
            ("m1", "baseline_m1.yaml", {})):
        c = load_config(os.path.join(ROOT, "configs", cfg_file),
                        overrides={"runtime": {"threads": 4}})
        out_dir = os.path.join(work, name)
        t = time.time()
        summ = train(c, out_dir, seed=0, max_train=6, epochs=n_epochs,
                     max_cases=n_cases, verbose=True)
        runs[name] = out_dir
        print("[3] %s: %d params, %d cases, 2 epochs in %.1f s (best val %.3f)"
              % (name, summ["n_params"], summ["train_size"], time.time() - t,
                 summ["best_val_loss"]))
        ok &= os.path.isfile(os.path.join(out_dir, "best.pt"))

    # ---- 4. baselines + metrics
    res = run_eval([runs["m3"], "m0", "m0g"], os.path.join(work, "eval"),
                   splits=["val"])
    import csv
    with open(res["metrics"], "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print("[4] metrics.csv rows=%d -> %s" % (len(rows), res["metrics"]))
    ok &= len(rows) > 0

    dt = time.time() - t0
    print("[5] total %.1f s (limit %.0f s)" % (dt, LIMIT_S))
    ok &= dt < LIMIT_S
    print("SMOKE %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
