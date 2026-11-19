# -*- coding: utf-8 -*-
"""Drive the generated r42r5 curved-array VBA through CST: build -> selfcheck ->
solve (HF TLM) -> 6-column complex far-field export.

The geometry, the material, the far-field monitor, the mesh settings and the
"ChangeSolverType HF TLM" block are taken VERBATIM from the generated .bas.
Only the runtime wrappers are ours (history block / _execute_vba_code).

Promoted from `_run_r42r5/run_case.py` on 2026-11-13 after it was validated on
three real cases (u0 / u1 / demo).  The phase gate came out at -178.4 deg vs the
unit library -177.6 deg, so this path produces trustworthy labels.

Usage:
  python cst/run_bas_case.py --bas <file.bas> --tag u0 --outdir <workdir>
"""
from __future__ import annotations

import argparse
import json
import glob
import os
import re
import sys
import time
import traceback
from datetime import datetime

# ---------------------------------------------------------------- CST python
# The CST python libraries live under <install>\AMD64\python_cst_libraries.
# Resolution order: --cst-lib  >  $CST_PYTHON_LIB  >  $CST_INSTALL_DIR  >
# auto-detected "CST Studio Suite*" under the usual Program Files roots  >
# whatever is already importable (e.g. when you run CST's own python).
def find_cst_lib(explicit=""):
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get("CST_PYTHON_LIB")
    if env:
        cands.append(env)
    inst = os.environ.get("CST_INSTALL_DIR")
    if inst:
        cands.append(os.path.join(inst, "AMD64", "python_cst_libraries"))
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
             os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
             r"D:\Program Files", r"D:\Program Files (x86)"]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for d in sorted(glob.glob(os.path.join(root, "CST Studio Suite*"))):
                cands.append(os.path.join(d, "AMD64", "python_cst_libraries"))
        except Exception:
            pass
    for c in cands:
        if c and os.path.isdir(c):
            return c
    return ""


CST_LIB = find_cst_lib()
if CST_LIB and CST_LIB not in sys.path:
    sys.path.insert(0, CST_LIB)

import cst.interface as ci  # noqa: E402


def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def split_bas(path):
    """Cut the generated macro into (geometry, solver-switch, export, selfcheck)."""
    lines = open(path, "r", encoding="ascii").read().splitlines()
    i0 = [i for i, l in enumerate(lines) if l.strip().lower().startswith("sub main")][0]
    i1 = [i for i, l in enumerate(lines) if l.strip().lower() == "end sub"][-1]
    body = lines[i0 + 1:i1]

    def find(pred, start=0):
        for i in range(start, len(body)):
            if pred(body[i]):
                return i
        raise RuntimeError("marker not found")

    i_solve = find(lambda l: "optional: solve" in l)
    build = body[:i_solve]
    i_chg = [i for i, l in enumerate(build) if l.strip().startswith("ChangeSolverType")][0]

    i_exp = find(lambda l: l.strip() == "If RUN_EXPORT Then")
    i_exp_end = find(lambda l: l.strip() == "End If", i_exp + 1)

    i_sc = find(lambda l: l.strip() == "If RUN_SELFCHECK Then")
    i_sc_end = max(i for i in range(i_sc, len(body)) if body[i].strip() == "End If")

    return (build[:i_chg], build[i_chg:],
            body[i_exp + 1:i_exp_end], body[i_sc + 1:i_sc_end])


def as_sub(code):
    return "Sub Main()\n" + "\n".join(code) + "\nEnd Sub\n"


def redirect(code, token, path):
    """Point the generated 'Open TOKEN For Output' at our own file."""
    out = []
    for line in code:
        s = line.strip()
        if s.startswith("Open ") and token in s:
            line = line.replace(token, '"%s"' % path)
        out.append(line)
    return out


def scan_model_log(data_dir):
    p = os.path.join(data_dir, "Result", "Model.log")
    info = {"file": p, "exists": os.path.isfile(p), "tlm_solver_lines": 0,
            "fit_solver_lines": 0, "head": [], "matches": []}
    if not info["exists"]:
        return info
    pat = re.compile(r"will be started|Module:|Solver type|TLM Solver|FIT|threads|"
                     r"living cells|total cell|steady state|Solver started", re.I)
    with open(p, "r", errors="replace") as fh:
        for line in fh:
            low = line.lower()
            if "tlm solver" in low:
                info["tlm_solver_lines"] += 1
            if "time domain solver (hex" in low or "(fit" in low or "fit solver" in low:
                info["fit_solver_lines"] += 1
            if pat.search(line):
                s = line.strip()
                if s and len(info["matches"]) < 120:
                    info["matches"].append(s[:220])
    info["head"] = info["matches"][:25]
    return info


def cells_from_file(data_dir):
    p = os.path.join(data_dir, "Result", "TLM_total_cell_count.txt")
    if os.path.isfile(p):
        try:
            return int(open(p).read().strip().split()[0])
        except Exception:
            return None
    return None


def run_case(de, bas_path, tag, outdir, ff_path, vol_path):
    rec = {"tag": tag, "bas": bas_path, "started_at": datetime.now().isoformat(timespec="seconds"),
           "status": "running", "steps": {}}
    geom, solver, export, selfcheck = split_bas(bas_path)
    log("%s: geometry %d lines, solver-switch %d, export %d, selfcheck %d"
        % (tag, len(geom), len(solver), len(export), len(selfcheck)))

    prj = None
    t_all = time.time()
    try:
        prj = de.new_mws()
        m = prj.model3d
        cst_path = os.path.join(outdir, "%s.cst" % tag)
        rec["project"] = cst_path

        # ---- 1. geometry (verbatim from the .bas) ------------------------
        t = time.time()
        m.add_to_history("r42r5 curved array (generated VBA)", "\n".join(geom), timeout=3600)
        rec["steps"]["build_s"] = round(time.time() - t, 1)
        rec["build_via"] = "add_to_history"
        log("%s: geometry built in %.1f s" % (tag, rec["steps"]["build_s"]))
        tree = list(m.get_tree_items())
        rec["tree_items"] = len(tree)
        rec["monitor_items"] = [x for x in tree if "farfield (f=" in x and "[pw]" in x]

        # ---- 2. solver switch (verbatim) ---------------------------------
        t = time.time()
        try:
            m.add_to_history("switch to HF TLM", "\n".join(solver), timeout=600)
            rec["solver_switch_via"] = "add_to_history"
        except Exception as exc:
            log("%s: history rejected the solver block (%s); using _execute_vba_code"
                % (tag, str(exc).replace(chr(10), " ")[:160]))
            m._execute_vba_code(as_sub(solver))
            rec["solver_switch_via"] = "_execute_vba_code"
        m._execute_vba_code('Sub Main()\n    ChangeSolverType "HF TLM"\nEnd Sub\n')
        rec["steps"]["solver_switch_s"] = round(time.time() - t, 1)

        # ---- 3. selfcheck volumes (no solve needed) ----------------------
        t = time.time()
        m._execute_vba_code(as_sub(redirect(selfcheck, "VOL_OUT", vol_path)))
        rec["steps"]["selfcheck_s"] = round(time.time() - t, 1)
        if os.path.isfile(vol_path):
            rec["selfcheck"] = open(vol_path, errors="replace").read()
        log("%s: selfcheck -> %s (%s bytes)"
            % (tag, vol_path, os.path.getsize(vol_path) if os.path.isfile(vol_path) else "MISSING"))

        prj.save(cst_path, include_results=False, allow_overwrite=True)
        data_dir = os.path.splitext(cst_path)[0]
        rec["data_dir"] = data_dir

        # ---- 4. mesh -----------------------------------------------------
        t = time.time()
        try:
            rec["cells"] = int(m.Mesh.GetNumberOfMeshCells())
            rec["mesh_nx"] = int(m.Mesh.GetNx())
            rec["mesh_ny"] = int(m.Mesh.GetNy())
            rec["mesh_nz"] = int(m.Mesh.GetNz())
        except Exception as exc:
            rec["cells_error_presolve"] = str(exc).replace(chr(10), " ")[:200]
        rec["steps"]["mesh_s"] = round(time.time() - t, 1)
        log("%s: pre-solve cells=%s (%s)" % (tag, rec.get("cells"),
                                             rec.get("cells_error_presolve", "ok")))

        # ---- 5. solve ----------------------------------------------------
        t = time.time()
        m.run_solver()
        rec["steps"]["solve_s"] = round(time.time() - t, 1)
        log("%s: SOLVED in %.1f s" % (tag, rec["steps"]["solve_s"]))

        if "cells" not in rec:
            try:
                rec["cells"] = int(m.Mesh.GetNumberOfMeshCells())
                rec["mesh_nx"] = int(m.Mesh.GetNx())
                rec["mesh_ny"] = int(m.Mesh.GetNy())
                rec["mesh_nz"] = int(m.Mesh.GetNz())
            except Exception as exc:
                rec["cells_error"] = str(exc).replace(chr(10), " ")[:200]
        rec["cells_from_file"] = cells_from_file(data_dir)

        # ---- 6. solver identity ------------------------------------------
        rec["model_log"] = scan_model_log(data_dir)
        rec["solver_type_probe"] = None
        for name in ("GetSolverType", "GetSolverTypeName"):
            try:
                rec["solver_type_probe"] = str(getattr(m.Solver, name)())
                break
            except Exception:
                continue

        # ---- 7. far-field export (verbatim) ------------------------------
        t = time.time()
        m._execute_vba_code(as_sub(redirect(export, "FF_OUT", ff_path)))
        rec["steps"]["export_s"] = round(time.time() - t, 2)
        rec["ff_file"] = ff_path
        rec["ff_bytes"] = os.path.getsize(ff_path) if os.path.isfile(ff_path) else 0
        log("%s: exported %s (%d bytes) in %.1f s"
            % (tag, ff_path, rec["ff_bytes"], rec["steps"]["export_s"]))

        rec["steps"]["total_s"] = round(time.time() - t_all, 1)
        rec["status"] = "ok"
    except Exception as exc:
        rec["status"] = "failed"
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        rec["traceback"] = traceback.format_exc()
        log("%s FAILED: %s\n%s" % (tag, rec["error"], rec["traceback"]))
    finally:
        if prj is not None:
            try:
                prj.save(include_results=True, allow_overwrite=True)
                rec["saved_with_results"] = True
            except Exception as exc:
                rec["saved_with_results"] = str(exc).replace(chr(10), " ")[:120]
            try:
                prj.close()
            except Exception:
                pass
        rec["finished_at"] = datetime.now().isoformat(timespec="seconds")
        with open(os.path.join(outdir, "run_%s.json" % tag), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bas", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ff", default="")
    ap.add_argument("--vol", default="")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    ff = args.ff or os.path.join(args.outdir, "ff_%s_10GHz.txt" % args.tag)
    vol = args.vol or os.path.join(args.outdir, "selfcheck_%s.txt" % args.tag)
    log("starting a NEW CST design environment ...")
    t = time.time()
    de = ci.DesignEnvironment.new()
    log("connected in %.1f s; CST version %s; pid %s"
        % (time.time() - t, de.version(), de.pid()))
    try:
        de.set_quiet_mode(True)
    except Exception:
        pass
    rec = run_case(de, args.bas, args.tag, args.outdir, ff, vol)
    log("result: %s" % rec["status"])
    try:
        de.close()
    except Exception as exc:
        log("de.close() failed: %s" % exc)
    return 0 if rec["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
