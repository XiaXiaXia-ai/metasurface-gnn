# -*- coding: utf-8 -*-
"""Freeze the file list and build the layout-grouped 70/15/15 split.

    python scripts/make_splits.py --out runs/splits.json

Writes runs/snapshot.json (sha256 manifest of every usable far-field file) and
runs/splits.json.  Pass both to training runs so that every model sees exactly the
same samples:

    python -m msgnn.train --config configs/train_m3.yaml --seed 0 \
        --snapshot runs/snapshot.json --splits runs/splits.json --out runs/m3_s0
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from msgnn.config import load_config
from msgnn.data.dataset import (Grid, build_snapshot, load_snapshot, make_splits,
                                save_snapshot, save_splits, scan_cases)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="make snapshot + splits")
    ap.add_argument("--config", default="configs/train_m3.yaml")
    ap.add_argument("--out", default="runs/splits.json")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--no-hash", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    grid = Grid.from_step(2.0)
    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    os.makedirs(out_dir, exist_ok=True)

    if args.snapshot:
        snap = load_snapshot(args.snapshot)
        snap_path = args.snapshot
    else:
        snap = build_snapshot(cfg.data, grid, hash_files=not args.no_hash,
                              block=cfg.physics.block, n_side=cfg.physics.n_side)
        snap_path = save_snapshot(snap, os.path.join(out_dir, "snapshot.json"))

    cases, warns = scan_cases(cfg.data, grid, snap, verbose=True,
                              block=cfg.physics.block, n_side=cfg.physics.n_side)
    splits = make_splits(cases, cfg.data.val_frac, cfg.data.test_frac,
                         cfg.data.split_seed)
    sp_path = save_splits(splits, args.out)

    by_idx = {c.idx: c for c in cases}
    print("snapshot : %s  (%d files)" % (snap_path, snap["n"]))
    print("splits   : %s  (seed %d, %d cases, %d layout groups)"
          % (sp_path, splits["seed"], splits["n_cases"], splits["n_groups"]))
    for k in ("train", "val", "test"):
        idxs = splits[k]
        spec = np.array([by_idx[i].specular for i in idxs], dtype=float)
        ones = np.array([by_idx[i].ones for i in idxs], dtype=float)
        print("  %-5s %4d cases (%4.1f%%)  specular %.2f +- %.2f dBsm  ones %4.1f%%"
              % (k, len(idxs), 100.0 * len(idxs) / max(len(cases), 1),
                 np.nanmean(spec), np.nanstd(spec), 100.0 * np.nanmean(ones)
                 / (cfg.physics.n_side ** 2)))
    if warns:
        print("  %d file(s) skipped during the scan" % len(warns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
