# -*- coding: utf-8 -*-
"""Evaluate the parameter-free M0 baseline and the M0g oracle.

    python scripts/run_baselines.py --config configs/train_m3.yaml \
        --snapshot runs/snapshot.json --splits-file runs/splits.json --out runs/baselines

M0  : q = q0 (isolated-cell Floquet library) through the vector radiation layer.
M0g : M0 plus ONE complex scalar per sample fitted on the label (2 real dof).
      Oracle, not a predictive model -- it answers 'how much of the gap can a
      single complex scalar explain', i.e. how much of M3's gain is the global
      common mode of theory/REPORT.md sec. 5.

Pass the same --snapshot/--splits-file as the training runs, otherwise the
baseline is scored on a different (later) file list.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from msgnn.evaluate import run_eval


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M0 / M0g baselines")
    ap.add_argument("--config", default="configs/train_m3.yaml")
    ap.add_argument("--out", default="runs/baselines")
    ap.add_argument("--splits", default="val,test")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--splits-file", default=None)
    args = ap.parse_args(argv)
    out = run_eval(["m0", "m0g"], args.out,
                   splits=[s.strip() for s in args.splits.split(",") if s.strip()],
                   cfg_path=args.config, snapshot_path=args.snapshot,
                   splits_path=args.splits_file)
    print("metrics -> %s" % out["metrics"])
    print("summary -> %s" % out["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
