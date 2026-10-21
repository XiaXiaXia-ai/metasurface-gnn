# -*- coding: utf-8 -*-
"""Sweep the Background surrounding space and compare result / cost.

Everything except BG_SPACE is identical (same 2x2 code, same radii, same mesh
rules, same monitors).  For each case we record:
    calculation box, hex cell count, wall-clock solve time, memory load,
    and the 10 GHz farfield on a 2 deg grid (theta 0..90, phi 0..358).
"""
import ctypes
import os
import sys
import threading
import time

import numpy as np

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

import build_coding_array as B

CASES = (5.0, 15.0, 30.0)
OUTDIR = r"D:\bg_sweep"
os.makedirs(OUTDIR, exist_ok=True)


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


def blocks_for(bg):
    out = []
    for cap, code in B.vba:
        if cap == "define background":
            code = ("""With Background
    .ResetBackground
    .Type "Normal"
    .Epsilon "1.0"
    .Mu "1.0"
    .XminSpace "%g"
    .XmaxSpace "%g"
    .YminSpace "%g"
    .YmaxSpace "%g"
    .ZminSpace "%g"
    .ZmaxSpace "%g"
End With
""" % ((bg,) * 6))
        out.append((cap, code))
    return out


FF_VBA = r'''Sub Main()
    Dim it, ip, i
    Dim a1, a3
    SelectTreeItem ("Farfields\farfield (f=10) [pw]")
    FarfieldPlot.Reset
    For it = 0 To 45
        For ip = 0 To 179
            FarfieldPlot.AddListEvaluationPoint it*2, ip*2, 0, "spherical", "frequency", 10000000000#
        Next ip
    Next it
    FarfieldPlot.CalculateList ""
    a1 = FarfieldPlot.GetList("Spherical linear theta abs")
    a3 = FarfieldPlot.GetList("Spherical linear phi abs")
    Open "%s" For Output As #1
    For it = 0 To 45
        For ip = 0 To 179
            i = it * 180 + ip
            Print #1, (it*2) & " " & (ip*2) & " " & a1(i) & " " & a3(i)
        Next ip
    Next it
    Close #1
End Sub'''


def analyse(path):
    d = np.loadtxt(path)
    th, rcs = d[:, 0], 10.0 * np.log10(10 ** (d[:, 2] / 10.0) + 10 ** (d[:, 3] / 10.0))
    spec = rcs[np.argmin(np.abs(th - 0.0))]
    far = th >= 10.0
    mean_far = 10.0 * np.log10(np.mean(10 ** (rcs[far] / 10.0)))
    return spec, mean_far, rcs.max()


def main():
    de = cst.interface.DesignEnvironment.connect_to_any()
    print("start, memory load %d%%" % mem_load(), flush=True)
    rows = []

    for bg in CASES:
        path = os.path.join(OUTDIR, "META_bg%g.cst" % bg)
        ff = os.path.join(OUTDIR, "ff_bg%g.txt" % bg)
        prj = None
        try:
            t0 = time.time()
            prj = de.new_mws()
            time.sleep(1.0)
            m = prj.model3d
            for cap, code in blocks_for(bg):
                m.add_to_history(cap, code, timeout=600)
            build_s = time.time() - t0
            prj.save(path, include_results=False, allow_overwrite=True)
            box = list(m.Boundary.GetCalculationBox())

            peak = [0]
            stop = threading.Event()

            def watch():
                while not stop.is_set():
                    peak[0] = max(peak[0], mem_load())
                    time.sleep(3.0)

            th = threading.Thread(target=watch, daemon=True)
            th.start()
            m0 = mem_load()
            t1 = time.time()
            m.run_solver()
            solve_s = time.time() - t1
            stop.set()
            th.join(timeout=2)

            cells = m.Mesh.GetNumberOfMeshCells()
            nx, ny, nz = m.Mesh.GetNx(), m.Mesh.GetNy(), m.Mesh.GetNz()
            prj.save(include_results=True, allow_overwrite=True)

            m._execute_vba_code(FF_VBA % ff)
            spec, mean_far, peak_ff = analyse(ff)

            rows.append((bg, box, cells, nx, ny, nz, build_s, solve_s,
                         m0, peak[0], spec, mean_far))
            print("[BG %4.1f] box %.0fx%.0fx%.0f mm | cells %d (%dx%dx%d) | "
                  "build %.0fs solve %.0fs | mem %d%%->%d%% | "
                  "specular %.2f dBsm, mean(theta>=10) %.2f dBsm"
                  % (bg, box[1] - box[0], box[3] - box[2], box[5] - box[4],
                     cells, nx, ny, nz, build_s, solve_s, m0, peak[0],
                     spec, mean_far), flush=True)
        except Exception as exc:  # noqa: BLE001
            print("[BG %4.1f] FAILED: %s" % (bg, str(exc).replace("\n", " ")[:200]), flush=True)
        finally:
            if prj is not None:
                try:
                    prj.close()
                except Exception:
                    pass

    if rows:
        print("\n%-6s %-22s %10s %8s %6s %10s %10s %10s"
              % ("BG", "calc box (mm)", "cells", "solve s", "mem%", "specular", "mean far", "peak far"))
        for r in rows:
            bg, box, cells, nx, ny, nz, bs, ss, m0, pk, spec, mean_far = r
            print("%-6.0f %-22s %10d %8.0f %6d %10.2f %10.2f %10.2f"
                  % (bg, "%.0fx%.0fx%.0f" % (box[1] - box[0], box[3] - box[2], box[5] - box[4]),
                     cells, ss, pk, spec, mean_far, spec))


if __name__ == "__main__":
    main()
