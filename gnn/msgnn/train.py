# -*- coding: utf-8 -*-
"""Training entry point (one run = one model x one seed).

    python -m msgnn.train --config configs/train_m3.yaml --seed 0 --out runs/m3_s0

What it writes into --out
    config.yaml          the fully resolved config (reproducibility)
    snapshot.json        the frozen far-field file list (sha256 manifest)
    splits.json          the layout-grouped split actually used
    normalizer.json      training-split feature statistics
    best.pt / last.pt    weights (+ config + metrics)
    history.csv          one row per epoch (losses, val metrics, seconds)
    summary.json         best epoch, parameter count, timings

Training policy
    * AdamW, cosine schedule, gradient clipping, early stopping on the validation
      loss (the same loss that trains -- never the test split);
    * the "best" checkpoint is chosen on validation only; the test split is
      touched by evaluate.py and by nothing else.
"""
import argparse
import csv
import json
import os
import shutil
import time
from typing import Dict, List, Optional

import numpy as np
import torch

from .config import Config, load_config
from .data.build_graph import collate
from .data.normalizer import Normalizer
from .evaluate import metrics_for_sample, summarize_rows
from .experiment import build_context, build_model, cast_batch
from .inference import predict_dataset
from .losses import build_loss


def _log(msg: str) -> None:
    print(msg, flush=True)


def train(cfg: Config, out_dir: str, seed: int = 0, max_train: int = 0,
          epochs: Optional[int] = None, verbose: bool = True, max_cases: int = 0,
          snapshot_path: Optional[str] = None,
          splits: Optional[dict] = None) -> dict:
    if cfg.model.name == "m0":
        raise ValueError("M0 has no trainable parameters -- evaluate it with "
                         "python -m msgnn.evaluate --runs m0")
    torch.manual_seed(int(seed))
    np.random.seed(int(seed))
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    ctx = build_context(cfg, out_dir, max_train=max_train, verbose=verbose,
                        max_cases=max_cases, snapshot_path=snapshot_path,
                        splits=splits)
    model = build_model(ctx)
    crit = build_loss(cfg.loss, ctx.grid.theta)
    n_par = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if verbose:
        _log("[train] %s  params=%d  dtype=%s  train=%d val=%d test=%d"
             % (cfg.model.name, n_par, ctx.dtype, len(ctx.ds["train"]),
                len(ctx.ds["val"]), len(ctx.ds["test"])))
    if n_par == 0:
        raise ValueError("model has no trainable parameters")

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=float(cfg.optim.lr),
                            weight_decay=float(cfg.optim.weight_decay))
    n_epochs = int(epochs or cfg.optim.epochs)
    sched = (torch.optim.lr_scheduler.CosineAnnealingLR(
        opt, T_max=max(n_epochs, 1), eta_min=float(cfg.optim.min_lr))
        if cfg.optim.scheduler == "cosine" else None)

    cfg.save(os.path.join(out_dir, "config.yaml"))
    if ctx.norm is not None:
        ctx.norm.save(os.path.join(out_dir, "normalizer.json"))
    # D5: when the caller passes --snapshot, build_context uses that file but does
    # not write it into the run directory; evaluate --runs <dir> then cannot find
    # out_dir/snapshot.json and aborts.  Freeze a copy here so every run is
    # self-contained and reproducible.
    _snap = os.path.join(out_dir, "snapshot.json")
    if (not os.path.isfile(_snap)) and ctx.snapshot_path \
            and os.path.isfile(ctx.snapshot_path):
        shutil.copyfile(ctx.snapshot_path, _snap)

    tr = ctx.ds["train"]
    va = ctx.ds["val"]
    if len(va) == 0:
        _log("[train] WARNING: empty validation split, early stopping disabled")
    bs = int(cfg.optim.batch_size)
    hist: List[dict] = []
    best = {"val_loss": float("inf"), "epoch": -1}
    bad = 0
    rng = np.random.default_rng(1000 + int(seed))

    for ep in range(1, n_epochs + 1):
        te = time.time()
        model.train()
        perm = rng.permutation(len(tr))
        tot, nseen = 0.0, 0
        for s in range(0, len(perm), bs):
            idx = [int(i) for i in perm[s:s + bs]]
            batch = cast_batch(collate(tr.select(idx)), ctx.dtype, ctx.device)
            out = model(batch)
            loss, parts = crit(out["sig_db"], batch["sig_db"])
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite loss at epoch %d" % ep)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            if cfg.optim.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad],
                    float(cfg.optim.grad_clip))
            opt.step()
            tot += float(loss) * len(idx)
            nseen += len(idx)
        train_loss = tot / max(nseen, 1)
        if sched is not None:
            sched.step()

        # ---- validation (never the test split)
        vres = {"loss": float("nan"), "rmse_db": float("nan"),
                "bias_db": float("nan"), "rho_db": float("nan")}
        if len(va) > 0:
            vp = predict_dataset(model, va, batch_size=bs, device=ctx.device,
                                 dtype=ctx.dtype)
            vpred = torch.as_tensor(vp["pred_db"], dtype=ctx.dtype)
            vtarg = torch.as_tensor(vp["targ_db"], dtype=ctx.dtype)
            vloss, vparts = crit(vpred, vtarg)
            rows = [metrics_for_sample(vp["pred_db"][i], vp["targ_db"][i],
                                       ctx.grid, cfg.eval) for i in range(len(vp["pred_db"]))]
            summ = summarize_rows(rows)
            vres = {"loss": float(vloss), "rmse_db": summ.get("rmse_db", float("nan")),
                    "bias_db": summ.get("bias_db", float("nan")),
                    "rho_db": summ.get("rho_db", float("nan"))}
            improved = float(vloss) < best["val_loss"] - 1e-9
        else:
            improved = train_loss < best["val_loss"]

        if improved:
            best = {"val_loss": float(vres["loss"] if len(va) else train_loss),
                    "epoch": ep}
            bad = 0
            torch.save({"model": model.state_dict(), "cfg": cfg.to_dict(),
                        "meta": {"epoch": ep, "seed": int(seed),
                                 "model": cfg.model.name, "n_params": int(n_par),
                                 "val_loss": best["val_loss"]}},
                       os.path.join(out_dir, "best.pt"))
        else:
            bad += 1
        lr = float(opt.param_groups[0]["lr"])
        row = {"epoch": ep, "lr": lr, "train_loss": train_loss,
               "val_loss": vres["loss"], "val_rmse_db": vres["rmse_db"],
               "val_bias_db": vres["bias_db"], "val_rho_db": vres["rho_db"],
               "secs": time.time() - te}
        hist.append(row)
        if verbose and (ep % max(int(cfg.runtime.log_every), 1) == 0):
            _log("[%3d] train %.4f | val %.4f  rmse %.2f dB  bias %+.2f  rho %.3f | %.1fs"
                 % (ep, train_loss, vres["loss"], vres["rmse_db"], vres["bias_db"],
                    vres["rho_db"], row["secs"]))
        if bad >= int(cfg.optim.patience) and len(va) > 0:
            _log("[train] early stop at epoch %d (patience %d)" % (ep, cfg.optim.patience))
            break

    torch.save({"model": model.state_dict(), "cfg": cfg.to_dict(),
                "meta": {"epoch": hist[-1]["epoch"], "seed": int(seed),
                         "model": cfg.model.name, "n_params": int(n_par),
                         "val_loss": hist[-1]["val_loss"]}},
               os.path.join(out_dir, "last.pt"))
    with open(os.path.join(out_dir, "history.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hist[0].keys()))
        w.writeheader()
        for r in hist:
            w.writerow(r)
    summary = {"model": cfg.model.name, "seed": int(seed), "n_params": int(n_par),
               "best_epoch": int(best["epoch"]), "best_val_loss": float(best["val_loss"]),
               "epochs_run": len(hist), "train_size": len(tr), "val_size": len(va),
               "test_size": len(ctx.ds["test"]),
               "wall_s": time.time() - t0,
               "dtype": str(ctx.dtype), "threads": int(cfg.runtime.threads)}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    if verbose:
        _log("[train] done in %.1f s -> %s" % (summary["wall_s"], out_dir))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="train one msgnn model")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="run directory")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=0)
    ap.add_argument("--max-train", type=int, default=0)
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--snapshot", default=None,
                    help="frozen file manifest (scripts/make_splits.py writes one)")
    ap.add_argument("--splits", default=None, help="splits.json to reuse")
    ap.add_argument("--tag", default="")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    out = args.out or os.path.join(cfg.out_dir, "%s%s_s%d"
                                   % (cfg.model.name, "_" + args.tag if args.tag else "",
                                      args.seed))
    split_dict = None
    if args.splits:
        from .data.dataset import load_splits
        split_dict = load_splits(args.splits)
    summary = train(cfg, out, seed=args.seed, max_train=args.max_train,
                    epochs=(args.epochs or None), verbose=not args.quiet,
                    max_cases=args.max_cases, snapshot_path=args.snapshot,
                    splits=split_dict)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
