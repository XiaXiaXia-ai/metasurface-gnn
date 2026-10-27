# -*- coding: utf-8 -*-
"""Generate the coding-metasurface dataset, resumably.

Layout
------
    D:\\dataset\\codes\\code_0000.txt        10 lines x 10 bits (2x2 macro cells)
    D:\\dataset\\results\\res_0000.json       metrics for that case
    D:\\dataset\\results\\ff\\ff_0000.txt     2 deg farfield, theta/phi/rcs_total
    D:\\dataset\\progress.jsonl              one JSON line per finished case
    D:\\dataset\\progress.log                human readable log
    D:\\dataset\\work\\                       scratch CST projects, deleted per case

A case is "done" only when res_<i>.json exists, and that file is written via a
.tmp + rename, so an interrupt can never leave a half-written result that would
be skipped on resume.  Re-running the same command simply continues: finished
cases are skipped, everything else is rebuilt from scratch.

    python dataset_gen.py                  # all 1000, continuing where it stopped
    python dataset_gen.py --limit 20       # at most 20 more cases
    python dataset_gen.py --start 100 --limit 50
    python dataset_gen.py --status
"""
import argparse
import ctypes
import gc
import json
import os
import random
import shutil
import sys
import time

import numpy as np

CST_LIB = r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries"
if CST_LIB not in sys.path:
    sys.path.insert(0, CST_LIB)

import cst.interface  # noqa: E402

import build_coding_array as B  # noqa: E402

ROOT = r"D:\dataset"
CODES = os.path.join(ROOT, "codes")
RESULTS = os.path.join(ROOT, "results")
FFDIR = os.path.join(RESULTS, "ff")
WORK = os.path.join(ROOT, "work")
PROGRESS_JSONL = os.path.join(ROOT, "progress.jsonl")
PROGRESS_LOG = os.path.join(ROOT, "progress.log")

TOTAL = 2000
SEED0 = 20261020
NB = B.N // B.BLOCK          # 10 x 10 bits
FF_FREQ = 10.0
FF_STEP = 2.0                # degrees; 46 x 180 = 8280 points
PLATE_DB = 19.34             # 4*pi*A^2/lambda^2 for the 280x280 plate at 10 GHz


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def mem_load():
    s = MEMORYSTATUSEX()
    s.dwLength = ctypes.sizeof(s)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return int(s.dwMemoryLoad)


def ensure_dirs():
    for d in (CODES, RESULTS, FFDIR, WORK):
        os.makedirs(d, exist_ok=True)


def make_code(i):
    rng = random.Random(SEED0 + i)
    return [[rng.randint(0, 1) for _ in range(NB)] for _ in range(NB)]


def expand(bits):
    return [[bits[m // B.BLOCK][n // B.BLOCK] for n in range(B.N)] for m in range(B.N)]


def code_text(bits):
    return "".join("".join(str(b) for b in row) + "\n" for row in bits)


def patches_vba(code20):
    out = []
    for m in range(B.N):
        for n in range(B.N):
            x = (m - (B.N - 1) / 2.0) * B.P
            y = (n - (B.N - 1) / 2.0) * B.P
            r = B.R1 if code20[m][n] else B.R0
            out.append("""With Cylinder
    .Reset
    .Name "patch_%02d_%02d"
    .Component "Array"
    .Material "PEC"
    .OuterRadius "%g"
    .InnerRadius "0"
    .Axis "z"
    .Zrange "%g", "%g"
    .Xcenter "%g"
    .Ycenter "%g"
    .Segments "0"
    .Create
End With
""" % (m, n, r, B.SUB_H, B.SUB_H, x, y))
    return "".join(out)


def blocks_for(code20):
    blocks = []
    for cap, code in B.vba:
        if cap == "build 400 patches":
            code = patches_vba(code20)
        blocks.append((cap, code))
    return blocks


FF_VBA = r'''Sub Main()
    Dim it, ip, i
    Dim a1, a3
    SelectTreeItem ("Farfields\farfield (f=%g) [pw]")
    FarfieldPlot.Reset
    For it = 0 To %d
        For ip = 0 To %d
            FarfieldPlot.AddListEvaluationPoint it*%g, ip*%g, 0, "spherical", "frequency", %.0f
        Next ip
    Next it
    FarfieldPlot.CalculateList ""
    a1 = FarfieldPlot.GetList("Spherical linear theta abs")
    a3 = FarfieldPlot.GetList("Spherical linear phi abs")
    Open "%s" For Output As #1
    For it = 0 To %d
        For ip = 0 To %d
            i = it * %d + ip
            Print #1, (it*%g) & " " & (ip*%g) & " " & a1(i) & " " & a3(i)
        Next ip
    Next it
    Close #1
End Sub'''


def ff_vba(path):
    nt = int(round(90.0 / FF_STEP))
    npp = int(round(360.0 / FF_STEP))
    return FF_VBA % (FF_FREQ, nt, npp - 1, FF_STEP, FF_STEP, FF_FREQ * 1e9,
                     path, nt, npp - 1, npp, FF_STEP, FF_STEP)


def analyse(path):
    d = np.loadtxt(path)
    th = d[:, 0]
    rcs = 10.0 * np.log10(10 ** (d[:, 2] / 10.0) + 10 ** (d[:, 3] / 10.0))
    spec = float(rcs[np.argmin(np.abs(th - 0.0))])
    far = th >= 10.0
    mean_far = float(10.0 * np.log10(np.mean(10 ** (rcs[far] / 10.0))))
    return spec, mean_far, float(rcs.max())


def atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def connect_de():
    """Connect (or start) the CST frontend in quiet mode: no modal dialogs."""
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    try:
        de.set_quiet_mode(True)
        log("quiet mode: %s" % de.in_quiet_mode())
    except Exception as exc:  # noqa: BLE001
        log("quiet mode FAILED: %s" % str(exc)[:120])
    return de


def close_leftovers(de):
    """Close scratch projects left behind by an interrupted run."""
    try:
        projects = de.get_open_projects()
    except Exception:
        return
    for p in projects:
        try:
            fn = p.filename()
        except Exception:
            fn = ""
        low = fn.lower()
        scratch = (not fn) or low.startswith(WORK.lower()) or \
                  ("cstde" in low and "untitled" in low)
        if scratch:
            try:
                p.close()
                log("closed leftover project %r" % fn)
            except Exception:
                pass
        else:
            log("note: leaving user project open: %s" % fn)


def done_count():
    return sum(1 for i in range(TOTAL)
               if os.path.isfile(os.path.join(RESULTS, "res_%04d.json" % i)))


def cleanup_work(i):
    p = os.path.join(WORK, "case_%04d.cst" % i)
    folder = os.path.join(WORK, "case_%04d" % i)
    for x in (p, p + ".tmp"):
        try:
            if os.path.isfile(x):
                os.remove(x)
        except OSError:
            pass
    try:
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
    except OSError:
        pass


def supervise(batch):
    """Run the worker in batches so its memory is released regularly.

    The COM proxy layer grows by ~14 MB per case inside the worker process;
    restarting the worker every `batch` cases keeps it small.
    """
    import subprocess
    while True:
        n = done_count()
        if n >= TOTAL:
            log("supervisor: all %d cases done" % TOTAL)
            return
        log("supervisor: %d/%d done, launching worker for up to %d cases"
            % (n, TOTAL, batch))
        rc = subprocess.call([sys.executable, "-u", os.path.abspath(__file__),
                              "--limit", str(batch)])
        if rc != 0:
            log("supervisor: worker exited %d, retrying in 30 s" % rc)
            time.sleep(30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--supervise", type=int, default=0, metavar="N",
                    help="batch mode: restart the worker every N cases")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    ensure_dirs()
    if args.status:
        n = done_count()
        print("finished %d / %d (%.1f%%)" % (n, TOTAL, 100.0 * n / TOTAL))
        return

    if args.supervise:
        supervise(args.supervise)
        return

    de = connect_de()
    close_leftovers(de)
    log("start  memory %d%%  done %d/%d" % (mem_load(), done_count(), TOTAL))

    times = []
    processed = 0

    for i in range(args.start, TOTAL):
        if args.limit and processed >= args.limit:
            break
        res_path = os.path.join(RESULTS, "res_%04d.json" % i)
        if os.path.isfile(res_path):
            continue
        code_path = os.path.join(CODES, "code_%04d.txt" % i)
        ff_path = os.path.join(FFDIR, "ff_%04d.txt" % i)
        ff_tmp = ff_path + ".tmp"

        bits = make_code(i)
        if not os.path.isfile(code_path):
            atomic_write(code_path, "# index %d  seed %d  block %dx%d\n%s"
                         % (i, SEED0 + i, B.BLOCK, B.BLOCK, code_text(bits)))
        code20 = expand(bits)

        prj = None
        t0 = time.time()
        try:
            prj = de.new_mws()
            time.sleep(0.5)
            m = prj.model3d
            for cap, code in blocks_for(code20):
                m.add_to_history(cap, code, timeout=600)

            t_solve = time.time()
            m.run_solver()
            solve_s = time.time() - t_solve

            m._execute_vba_code(ff_vba(ff_tmp))
            spec, mean_far, mx = analyse(ff_tmp)
            os.replace(ff_tmp, ff_path)

            rec = dict(index=i, seed=SEED0 + i, block=B.BLOCK,
                       code="".join("".join(str(b) for b in r) for r in bits),
                       freq_ghz=FF_FREQ, ff_step=FF_STEP,
                       specular_dbsm=round(spec, 3),
                       reduction_db=round(spec - PLATE_DB, 3),
                       mean_far_dbsm=round(mean_far, 3),
                       max_dbsm=round(mx, 3),
                       solve_s=round(solve_s, 1),
                       wall_s=round(time.time() - t0, 1),
                       mem_pct=mem_load(),
                       done=time.strftime("%Y-%m-%d %H:%M:%S"))
            atomic_write(res_path, json.dumps(rec, ensure_ascii=False) + "\n")
            with open(PROGRESS_JSONL, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())

            times = (times + [time.time() - t0])[-20:]
            avg = sum(times) / len(times)
            left = TOTAL - done_count()
            log("case %04d  spec %6.2f dBsm  red %6.2f dB  %.0fs  mem %d%%  "
                "(avg %.0fs, ~%.1f h left)"
                % (i, spec, spec - PLATE_DB, time.time() - t0, mem_load(),
                   avg, left * avg / 3600.0))
        except Exception as exc:  # noqa: BLE001
            log("case %04d FAILED after %.0fs: %s"
                % (i, time.time() - t0, str(exc).replace("\n", " ")[:160]))
            try:
                de = connect_de()
            except Exception:
                pass
        finally:
            if prj is not None:
                try:
                    prj.close()
                except Exception:
                    pass
            cleanup_work(i)
            del prj
            gc.collect()
            processed += 1

    log("run finished, %d/%d done" % (done_count(), TOTAL))


if __name__ == "__main__":
    main()
