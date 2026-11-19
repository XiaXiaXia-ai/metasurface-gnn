"""Batch generator for the r=4.2/5.0 curved-array dataset.

One knob for the array size, one knob for how many cases to run::

    python cst/curved_batch.py --n 8 --count 20 --R 200 --out D:/GNN/_batch/n8_R200
    python cst/curved_batch.py --cells 64 --count 20 --R 200 --out D:/GNN/_batch/n8_R200
    python cst/curved_batch.py --n 8 --count 20 --dry-run --out D:/GNN/_batch/n8_R200
    python cst/curved_batch.py --n 8 --count 20 --gate --R 200 --out D:/GNN/_batch/n8_R200

The model itself comes from cst/r42r5_curved.py (audited: 64 patches at 64 distinct
positions, TLM, 6-column export).  This file only adds the batch loop, resume logic,
per-case metadata and the quality gate.

Output layout:

    <out>/meta.json                unit id, parameters, fingerprint
    <out>/codes/code_XXXX.txt
    <out>/results/res_XXXX.json
    <out>/results/ff/ff_XXXX.txt
    <out>/work/case_XXXX.bas       the macro that was run
    <out>/work/case_XXXX.cst       the project
    <out>/logs/progress.jsonl
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import r42r5_curved as B                              # noqa: E402

UNIT_ID = "r42r5"
SPEED_OF_LIGHT_MM_GHZ = 299.792458     # c / 1 GHz, in mm
PLATE_DBSM_CACHE = {}


def side_from_args(args):
    if args.cells:
        n = int(round(args.cells ** 0.5))
        if n * n != args.cells:
            raise SystemExit("--cells must be a perfect square (got %d)" % args.cells)
        if args.n and args.n != n:
            raise SystemExit("--n %d and --cells %d disagree" % (args.n, args.cells))
        return n
    if not args.n:
        raise SystemExit("give --n (side length) or --cells (total elements)")
    return args.n


def make_code(n_side, block, index, seed, kind="random"):
    if kind != "random":
        return kind
    nbit = n_side // block
    rng = np.random.default_rng([seed, index])
    bits = rng.integers(0, 2, size=(nbit, nbit))
    return "".join(str(int(v)) for v in bits.ravel())


def fingerprint(params):
    blob = json.dumps(params, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def plate_dbsm(n_side, period, freq):
    key = (n_side, period, freq)
    if key not in PLATE_DBSM_CACHE:
        lam = SPEED_OF_LIGHT_MM_GHZ / freq
        a = (n_side * period) * 1e-3
        PLATE_DBSM_CACHE[key] = 10.0 * np.log10(4.0 * np.pi * a ** 4 / (lam * 1e-3) ** 2)
    return PLATE_DBSM_CACHE[key]


def analyse(ff_path):
    d = np.loadtxt(ff_path)
    if d.ndim != 2 or d.shape[1] != 6:
        raise ValueError("expected 6 columns, got %r" % (d.shape,))
    if d.shape[0] != 8280:
        raise ValueError("expected 8280 rows, got %d" % d.shape[0])
    if not np.isfinite(d).all():
        raise ValueError("non-finite values in %s" % ff_path)
    sig = 10.0 * np.log10(10.0 ** (d[:, 2] / 10.0) + 10.0 ** (d[:, 4] / 10.0))
    th = d[:, 0]
    far = (th >= 10.0) & (th <= 90.0)
    return {
        "specular_dbsm": float(sig[0]),
        "max_dbsm": float(sig.max()),
        "mean_far_dbsm": float(10.0 * np.log10(np.mean(10.0 ** (sig[far] / 10.0)))),
        "arg_Eth_deg": float(d[0, 3]),
        "ff_rows": int(d.shape[0]),
    }


def run_case_subprocess(bas_path, tag, workdir, ff_path, vol_path):
    """Run one .bas through CST in a fresh process.

    Delegates to cst/run_bas_case.py (validated on three real cases).  One
    process per case keeps the CST COM proxy from growing across a long batch.
    """
    import subprocess

    runner = os.path.join(HERE, "run_bas_case.py")
    cmd = [sys.executable, runner, "--bas", bas_path, "--tag", tag,
           "--outdir", workdir, "--ff", ff_path, "--vol", vol_path]
    p = subprocess.run(cmd, capture_output=True, text=True)
    rec_path = os.path.join(workdir, "run_%s.json" % tag)
    rec = {}
    if os.path.exists(rec_path):
        try:
            rec = json.load(open(rec_path, encoding="utf-8"))
        except Exception:
            rec = {}
    rec["returncode"] = p.returncode
    if p.returncode != 0 or rec.get("status") != "ok":
        rec["status"] = "failed"
        rec["stderr_tail"] = (p.stderr or "")[-1200:]
    return rec


def cpu_count_default():
    return os.cpu_count() or 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=0, help="elements per side (e.g. 8)")
    ap.add_argument("--cells", type=int, default=0,
                    help="total elements (e.g. 64); must be a perfect square")
    ap.add_argument("--count", type=int, default=1, help="how many cases to run")
    ap.add_argument("--start", type=int, default=0, help="first case index")
    ap.add_argument("--R", type=float, default=200.0, help="cylinder radius (mm)")
    ap.add_argument("--P", type=float, default=14.0)
    ap.add_argument("--block", type=int, default=2)
    ap.add_argument("--r0", type=float, default=5.0)
    ap.add_argument("--r1", type=float, default=4.2)
    ap.add_argument("--sub-h", type=float, default=1.5)
    ap.add_argument("--er", type=float, default=2.65)
    ap.add_argument("--tand", type=float, default=0.0013)
    ap.add_argument("--solver", default="tlm", choices=("tlm", "fit"))
    ap.add_argument("--code-kind", default="random",
                    choices=("random", "uniform0", "uniform1"))
    ap.add_argument("--seed", type=int, default=20261113)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true", help="write .bas only, no CST")
    ap.add_argument("--gate", action="store_true",
                    help="run uniform0/uniform1 first and check the phase difference")
    ap.add_argument("--gate-tol", type=float, default=5.0,
                    help="allowed |delta-phi - 177.63| in degrees")
    args = ap.parse_args(argv)

    n_side = side_from_args(args)
    if n_side % args.block:
        raise SystemExit("block must divide n")

    out = os.path.abspath(args.out)
    work = os.path.join(out, "work")
    for sub in ("codes", "results", "results/ff", "work", "logs"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    params = dict(unit_id=UNIT_ID, n_side=n_side, block=args.block, R_mm=args.R,
                  period_mm=args.P, r0=args.r0, r1=args.r1, sub_h=args.sub_h,
                  er=args.er, tand=args.tand, solver=args.solver,
                  freq_ghz=10.0, ff_step_deg=2.0)
    fp = fingerprint(params)

    meta_path = os.path.join(out, "meta.json")
    if os.path.exists(meta_path):
        old = json.load(open(meta_path, encoding="utf-8"))
        if old.get("fingerprint") != fp:
            raise SystemExit(
                "meta.json fingerprint %s != %s: this directory holds a different "
                "unit/geometry.  Use a new --out, or delete it deliberately."
                % (old.get("fingerprint"), fp))
    else:
        json.dump(dict(params, fingerprint=fp,
                       created=time.strftime("%Y-%m-%d %H:%M:%S")),
                  open(meta_path, "w", encoding="utf-8"), indent=2)

    prog = open(os.path.join(out, "logs", "progress.jsonl"), "a", encoding="utf-8")

    def log(**kw):
        kw["t"] = time.strftime("%Y-%m-%d %H:%M:%S")
        prog.write(json.dumps(kw, ensure_ascii=True) + "\n")
        prog.flush()

    gate_info = {}
    if args.gate:
        print("== gate: uniform0 / uniform1 (delta-phi @ theta=0) ==", flush=True)
        ph = {}
        for kind in ("uniform0", "uniform1"):
            ff = os.path.join(out, "results", "ff", "gate_%s.txt" % kind)
            vba = B.build_vba(n_side=n_side, radius=args.R, period=args.P,
                              sub_h=args.sub_h, er=args.er, tan_d=args.tand,
                              r0=args.r0, r1=args.r1, code=kind, block=args.block,
                              solver=args.solver, run_solver=not args.dry_run,
                              run_export=not args.dry_run, run_selfcheck=True,
                              ff_out=ff)
            bas = os.path.join(out, "work", "gate_%s.bas" % kind)
            open(bas, "w", encoding="ascii", newline="\r\n").write(vba)
            if args.dry_run:
                continue
            t0 = time.time()
            rr = run_case_subprocess(bas, "gate_%s" % kind, work, ff,
                                     os.path.join(work, "selfcheck_gate_%s.txt" % kind))
            if rr.get("status") != "ok":
                raise SystemExit("gate %s failed: %s"
                                 % (kind, rr.get("error") or rr.get("stderr_tail")))
            r = analyse(ff)
            ph[kind] = r["arg_Eth_deg"]
            print("   %-9s spec %8.3f dBsm   argEth %+8.2f deg   %.0f s"
                  % (kind, r["specular_dbsm"], r["arg_Eth_deg"], time.time() - t0),
                  flush=True)
            log(kind=kind, gate=True, **r)
        if not args.dry_run:
            dphi = (ph["uniform1"] - ph["uniform0"] + 180.0) % 360.0 - 180.0
            err = abs(abs(dphi) - 177.63)
            gate_info = dict(dphi_deg=dphi, err_deg=err, tol=args.gate_tol,
                             passed=bool(err <= args.gate_tol))
            print("   delta-phi = %+7.2f deg (expect -177.63 +- %.1f) -> %s"
                  % (dphi, args.gate_tol, "PASS" if gate_info["passed"] else "FAIL"),
                  flush=True)
            json.dump(dict(gate=gate_info), open(os.path.join(out, "gate.json"), "w"),
                      indent=2)
            if not gate_info["passed"]:
                raise SystemExit("gate failed: wrong solver or wrong unit radii; "
                                 "fix before batch-running.")

    for i in range(args.start, args.start + args.count):
        res_path = os.path.join(out, "results", "res_%04d.json" % i)
        ff = os.path.join(out, "results", "ff", "ff_%04d.txt" % i)
        if os.path.exists(res_path) and os.path.exists(ff):
            try:
                analyse(ff)
                print("case %04d  skip (done)" % i, flush=True)
                continue
            except Exception:
                pass
        code = make_code(n_side, args.block, i, args.seed, args.code_kind)
        open(os.path.join(out, "codes", "code_%04d.txt" % i), "w").write(code + "\n")
        tag = "c%04d" % i
        bas = os.path.join(work, "case_%04d.bas" % i)
        run_json = os.path.join(work, "run_%s.json" % tag)

        # If CST already produced both the export and a successful runner
        # record, rebuild the dataset entry from them instead of solving again.
        salvaged = None
        if os.path.exists(ff) and os.path.exists(run_json):
            try:
                rr0 = json.load(open(run_json, encoding="utf-8"))
                if rr0.get("status") == "ok":
                    salvaged = (analyse(ff), rr0)
            except Exception:
                salvaged = None

        if salvaged is None:
            vba = B.build_vba(n_side=n_side, radius=args.R, period=args.P,
                              sub_h=args.sub_h, er=args.er, tan_d=args.tand,
                              r0=args.r0, r1=args.r1, code=code, block=args.block,
                              solver=args.solver, run_solver=not args.dry_run,
                              run_export=not args.dry_run, run_selfcheck=True,
                              ff_out=ff)
            open(bas, "w", encoding="ascii", newline="\r\n").write(vba)
            if args.dry_run:
                print("case %04d  wrote %s" % (i, bas), flush=True)
                continue
            t0 = time.time()
            try:
                rr = run_case_subprocess(bas, tag, work, ff,
                                         os.path.join(work, "selfcheck_%04d.txt" % i))
                if rr.get("status") != "ok":
                    raise RuntimeError(rr.get("error") or rr.get("stderr_tail")
                                       or "runner failed")
                r = analyse(ff)
                wall = time.time() - t0
            except Exception as exc:
                print("case %04d  FAILED: %r" % (i, exc), flush=True)
                log(index=i, error=repr(exc))
                continue
        else:
            r, rr = salvaged
            wall = float(rr.get("steps", {}).get("total_s") or 0.0)
            print("case %04d  recovered from existing ff + run json (no re-solve)"
                  % i, flush=True)
        rec = dict(index=i, n=n_side, block=args.block, r0=args.r0, r1=args.r1,
                   code=code, unit_id=UNIT_ID, fingerprint=fp,
                   specular_dbsm=round(r["specular_dbsm"], 3),
                   max_dbsm=round(r["max_dbsm"], 3),
                   mean_far_dbsm=round(r["mean_far_dbsm"], 3),
                   plate_dbsm=round(plate_dbsm(n_side, args.P, 10.0), 3),
                   wall_s=round(wall, 1), solver=args.solver,
                   cells=rr.get("cells_from_file") or rr.get("cells"),
                   tlm_lines=(rr.get("model_log") or {}).get("tlm_solver_lines"),
                   solve_s=rr.get("steps", {}).get("solve_s"),
                   done=time.strftime("%Y-%m-%d %H:%M:%S"))
        rec["reduction_db"] = round(rec["specular_dbsm"] - rec["plate_dbsm"], 3)
        json.dump(rec, open(res_path, "w", encoding="utf-8"), indent=2)
        print("case %04d  spec %8.3f  max %8.3f  %5.0f s"
              % (i, rec["specular_dbsm"], rec["max_dbsm"], wall), flush=True)
        log(**rec)

    prog.close()

    # Every export must have a matching record.  A silent indentation slip once
    # wrote 200 ff files with zero res.json; this check is what catches it.
    orphans = []
    for ff_path in sorted(glob.glob(os.path.join(out, "results", "ff", "ff_*.txt"))):
        stem = os.path.basename(ff_path)[3:-4]
        if not os.path.exists(os.path.join(out, "results", "res_%s.json" % stem)):
            orphans.append(ff_path)
    if orphans:
        raise SystemExit("inconsistent dataset: %d ff without res json (e.g. %s)"
                         % (len(orphans), orphans[0]))

    print("\nmeta: %s\nfingerprint: %s" % (meta_path, fp))
    print("records: %d" % len(glob.glob(os.path.join(out, "results", "res_*.json"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())