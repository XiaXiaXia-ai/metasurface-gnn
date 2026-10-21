# -*- coding: utf-8 -*-
"""Export the 3D farfields of a solved CST project at an arbitrary angular step.

Why not CST's ASCII export: for a plane-wave farfield monitor the built-in ASCII
/ .ffs export always dumps the grid that was stored at solve time (5 deg here),
and FarfieldPlot.Step has no effect on it.  The documented list API does
evaluate at arbitrary angles, so we drive that instead:

    FarfieldPlot.AddListEvaluationPoint(theta, phi, 0, "spherical",
                                        "frequency", f_Hz)
    FarfieldPlot.CalculateList ""
    FarfieldPlot.GetList("Spherical linear theta abs" | ... phase)

Output: one text file per monitor, 6 columns, no header:

    theta[deg]  phi[deg]  E_theta[dBsm]  phase(E_theta)[deg]
                          E_phi[dBsm]    phase(E_phi)[deg]

The total RCS follows as 10*log10(10^(Eth/10) + 10^(Eph/10)); postprocess_farfield.py
does that (it also still reads CST's native 8-column tables).

Run this AFTER the solver has finished.
"""
import os
import sys
import time

CST_LIB = r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries"
if os.path.isdir(CST_LIB) and CST_LIB not in sys.path:
    sys.path.insert(0, CST_LIB)

import cst.interface  # noqa: E402

PROJECT = r"D:\META_coding_array_er265_r2_b2.cst"
OUTDIR = r"D:\ff_er265_r2_b2"
FREQS = (9.8, 9.9, 10.0, 10.1, 10.2)
STEP = 1.0          # degrees; 1.0 -> 181 x 360 points, ~2.6 s per frequency


def find_project(de):
    target = os.path.abspath(PROJECT).lower()
    for prj in de.get_open_projects():
        try:
            if os.path.abspath(prj.filename()).lower() == target:
                return prj
        except Exception:
            pass
    raise SystemExit("project not open in CST: %s" % PROJECT)


def vba_for(freq, path, step):
    nt = int(round(180.0 / step))
    np_ = int(round(360.0 / step))
    return '''Sub Main()
    Dim it, ip, i
    Dim a1, a2, a3, a4
    SelectTreeItem ("Farfields\\farfield (f=%g) [pw]")
    FarfieldPlot.Reset
    For it = 0 To %d
        For ip = 0 To %d
            FarfieldPlot.AddListEvaluationPoint it*%g, ip*%g, 0, "spherical", "frequency", %.0f
        Next ip
    Next it
    FarfieldPlot.CalculateList ""
    a1 = FarfieldPlot.GetList("Spherical linear theta abs")
    a2 = FarfieldPlot.GetList("Spherical linear theta phase")
    a3 = FarfieldPlot.GetList("Spherical linear phi abs")
    a4 = FarfieldPlot.GetList("Spherical linear phi phase")
    Open "%s" For Output As #1
    For it = 0 To %d
        For ip = 0 To %d
            i = it * %d + ip
            Print #1, (it*%g) & " " & (ip*%g) & " " & a1(i) & " " & a2(i) & " " & a3(i) & " " & a4(i)
        Next ip
    Next it
    Close #1
End Sub''' % (freq, nt, np_ - 1, step, step, freq * 1e9,
              path, nt, np_ - 1, np_, step, step)


def main():
    de = cst.interface.DesignEnvironment.connect_to_any()
    prj = find_project(de)
    prj.activate()
    m3d = prj.model3d
    print("project:", prj.filename())
    print("grid   : %.1f deg -> %d x %d points, %.1f s per frequency"
          % (STEP, int(round(180 / STEP)) + 1, int(round(360 / STEP)), 2.6), flush=True)

    have = set(m3d.get_tree_items())
    os.makedirs(OUTDIR, exist_ok=True)

    for f in FREQS:
        name = "farfield (f=%g) [pw]" % f
        if "Farfields\\" + name not in have:
            print("  [miss] %-28s not in the tree (solver not run?)" % name)
            continue
        path = os.path.join(OUTDIR, "ff_%g.txt" % f)
        t0 = time.time()
        try:
            m3d._execute_vba_code(vba_for(f, path, STEP))
        except Exception as exc:  # noqa: BLE001
            print("  [fail] %-28s %s" % (name, str(exc).replace("\n", " ")[-150:]))
            continue
        n = sum(1 for _ in open(path, "r", errors="replace"))
        print("  [ok]   %-28s %5.1fs  %6d points  %.1f MB"
              % (name, time.time() - t0, n, os.path.getsize(path) / 1e6), flush=True)

    print("done ->", OUTDIR)


if __name__ == "__main__":
    main()
