# -*- coding: utf-8 -*-
"""ESS coding-array dataset: 2x2 macro modules, TLM solver, DEFAULT TLM mesh.

nsub = number of ESS sub-cells per side (10 or 16)  ->  macro = nsub/2 (5 or 8)
Array size = nsub * 15 mm (150 mm or 240 mm).

Usage:
    python ess_dataset.py --n 10 --total 100 --root D:\\dataset_ess10 [--once]
"""
import argparse
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

P, SUB, H = 15.0, 2, 3.0
RING_W, BAR_W = 0.5, 1.0
RS, LS = 3.0, 0.45e-9
FMIN, FMAX, FMON = 8.0, 12.0, 10.0
BG = 15.0
FF_STEP = 2.0
C0 = 299792458.0
CODE4 = [[1, 1, 1, 1],
         [0, 1, 0, 1],
         [0, 1, 0, 1],
         [1, 1, 1, 0]]


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(ROOT, "progress.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def mem_load():
    try:
        import subprocess
        out = subprocess.run(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/format:list"],
                             capture_output=True, text=True, timeout=10).stdout
        d = dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)
        tot = float(d["TotalVisibleMemorySize"])
        free = float(d["FreePhysicalMemory"])
        return int(100 * (1 - free / tot))
    except Exception:
        return -1


def brick(nm, comp, x0, x1, y0, y1, z0="0", z1="0", mat="PEC"):
    return """    With Brick
        .Reset
        .Name "%s"
        .Component "%s"
        .Material "%s"
        .Xrange "%g", "%g"
        .Yrange "%g", "%g"
        .Zrange "%s", "%s"
        .Create
    End With""" % (nm, comp, mat, x0, x1, y0, y1, z0, z1)


def module1_vba():
    out = []
    for s, (sx, sy) in enumerate(((-7.5, -7.5), (7.5, -7.5), (-7.5, 7.5), (7.5, 7.5))):
        for i in range(4):
            for j in range(4):
                if CODE4[i][j] != 1:
                    continue
                x0 = -(4 - j) * 1.5 - BAR_W / 2.0
                x1 = x0 + 1.5
                y1 = (4 - i) * 1.5
                y0 = y1 - 1.5
                for k, (mx, my) in enumerate(((1, -1), (-1, -1), (1, 1), (-1, 1))):
                    ax, bx = sorted((sx + mx * x0, sx + mx * x1))
                    ay, by = sorted((sy + my * y0, sy + my * y1))
                    out.append(brick("p_%d_%02d_%02d_%d" % (s, i, j, k), "mod1", ax, bx, ay, by))
        h, r = P / 2.0, P / 2.0 - RING_W
        for k, (x0, x1, y0, y1) in enumerate([
                (sx - h, sx + h, sy - h, sy - r), (sx - h, sx + h, sy + r, sy + h),
                (sx - h, sx - r, sy - r, sy + r), (sx + r, sx + h, sy - r, sy + r)]):
            out.append(brick("ring_%d_%d" % (s, k), "mod1", x0, x1, y0, y1))
        for k, (y0, y1) in enumerate(((sy, sy + 6.0), (sy - 6.0, sy))):
            out.append(brick("bar_%d_%d" % (s, k), "mod1", sx - BAR_W / 2, sx + BAR_W / 2, y0, y1))
    return "\n".join(out)


def lump_vba(cx, cy, s):
    out = []
    for k, (y1, y2) in enumerate(((7.0, 6.0), (-7.0, -6.0))):
        out.append("""    With LumpedElement
        .Reset
        .SetName "lump_%g_%g_%d_%d"
        .Folder "Folder1"
        .SetType "RLCSerial"
        .SetR "%g"
        .SetL "%g"
        .SetC "0"
        .SetGs "0"
        .SetI0 "1e-14"
        .SetT "300"
        .SetMonitor "True"
        .SetRadius "0.0"
        .CircuitFileName ""
        .CircuitId "1"
        .UseCopyOnly "True"
        .UseRelativePath "False"
        .SetP1 "False", "%g", "%g", "0"
        .SetP2 "False", "%g", "%g", "0"
        .SetInvert "False"
        .Wire ""
        .Position "end1"
        .Create
    End With""" % (cx, cy, s, k, RS, LS, cx, cy + y1, cx, cy + y2))
    return "\n".join(out)


def copy_vba(src, dx, dy):
    return """Sub Main()
    With Transform
        .Reset
        .Name "%s"
        .Transform "Shape", "Matrix"
        .Matrix 1, 0, 0, 0, 1, 0, 0, 0, 1
        .Vector %g, %g, 0
        .MultipleObjects "True"
        .GroupObjects "False"
        .Repetitions "1"
        .MultipleSelection "False"
        .Destination ""
        .Material ""
        .AutoDestination "True"
        .Transform "Shape", "Translate"
        .UsePickedPoints "False"
        .Vector %g, %g, 0
    End With
End Sub""" % (src, dx, dy, dx, dy)


def build_case(prj, nsub, code, minstep=0.35):
    """Build one array; moderately refined TLM mesh, plane wave, farfield monitor."""
    macro = nsub // 2
    L = nsub * P
    half = L / 2.0
    m = prj.model3d
    blocks = [
        ("units", """With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
    .SetUnit "Time", "ns"
End With"""),
        ("freq", 'Solver.FrequencyRange "%g", "%g"' % (FMIN, FMAX)),
        ("background", """With Background
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
End With""" % ((BG,) * 6)),
        ("boundary", """With Boundary
    .Xmin "expanded open"
    .Xmax "expanded open"
    .Ymin "expanded open"
    .Ymax "expanded open"
    .Zmin "expanded open"
    .Zmax "expanded open"
    .Xsymmetry "none"
    .Ysymmetry "none"
    .Zsymmetry "none"
End With"""),
        ("substrate", brick("substrate", "Array", -half, half, -half, half, -H, "0", "Vacuum")),
        ("ground", brick("ground", "Array", -half, half, -half, half, -H, -H)),
        ("mod0", brick("metal0", "mod0", -SUB * P / 2, SUB * P / 2, -SUB * P / 2, SUB * P / 2)),
        ("mod1", module1_vba()),
    ]
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=600)

    # merge the 2x2 module metal into ONE solid before copying
    names = ["mod1:" + i.split("\\")[-1] for i in m.get_tree_items() if i.startswith("Components\\mod1\\")]
    lines = ["Sub Main()"]
    for nm in names[1:]:
        lines.append("    On Error Resume Next")
        lines.append('    Solid.Add "%s", "%s"' % (names[0], nm))
    lines.append("End Sub")
    m._execute_vba_code("\n".join(lines))

    lumps = ["Sub Main()"]
    for mm in range(macro):
        for nn in range(macro):
            cx = (mm - (macro - 1) / 2.0) * SUB * P
            cy = (nn - (macro - 1) / 2.0) * SUB * P
            if code[mm][nn]:
                m._execute_vba_code(copy_vba("mod1", cx, cy))
                for s, (dx, dy) in enumerate(((-7.5, -7.5), (7.5, -7.5), (-7.5, 7.5), (7.5, 7.5))):
                    lumps.append(lump_vba(cx + dx, cy + dy, s))
            else:
                m._execute_vba_code(copy_vba("mod0", cx, cy))
    lumps.append("End Sub")
    m._execute_vba_code("\n".join(lumps))

    # drop the origin templates
    dele = ["Sub Main()"]
    for i in m.get_tree_items():
        if i.startswith("Components\\mod1\\") or i.startswith("Components\\mod0\\"):
            dele.append('    Solid.Delete "%s"' % i.split("Components\\")[1].replace("\\", ":"))
    dele.append("End Sub")
    m._execute_vba_code("\n".join(dele))

    m.add_to_history("mesh settings", """With Mesh
    .MeshType "HexahedralTLM"
End With
With MeshSettings
    .SetMeshType "HexTLM"
    .Set "StepsPerWaveNear", "30"
    .Set "StepsPerWaveFar", "15"
    .Set "WavelengthRefinementSameAsNear", "0"
    .Set "StepsPerBoxNear", "60"
    .Set "StepsPerBoxFar", "1"
    .Set "ModelBoxDescrNear", "maxedge"
    .Set "ModelBoxDescrFar", "maxedge"
    .Set "UseRatioLimitGeometry", "0"
    .Set "UseSameMinStepGeometryXYZ", "1"
    .Set "MinStepGeometryX", "%g"
    .Set "MinStepGeometryY", "%g"
    .Set "MinStepGeometryZ", "%g"
    .Set "EdgeRefinementOn", "1"
    .Set "EdgeRefinementPolicy", "1"
    .Set "EdgeRefinementRatio", "2"
    .Set "EdgeRefinementBufferLines", "2"
    .Set "RefineEdgeMaterialGlobal", "1"
End With""" % (minstep, minstep, minstep), timeout=600)

    m.add_to_history("plane wave", """With PlaneWave
    .Reset
    .Normal "0", "0", "-1"
    .EVector "1", "0", "0"
    .Polarization "Linear"
    .ReferenceFrequency "%g"
    .PhaseDifference "0.0"
    .CircularDirection "Left"
    .AxialRatio "0.0"
    .SetUserDecouplingPlane "False"
    .Store
End With""" % FMON, timeout=600)
    m.add_to_history("farfield monitor", """With Monitor
    .Reset
    .Name "farfield (f=%g)"
    .Domain "Frequency"
    .FieldType "Farfield"
    .MonitorValue "%g"
    .UseSubvolume "False"
    .ExportFarfieldSource "False"
    .Create
End With""" % (FMON, FMON), timeout=600)
    m.add_to_history("solver", """With Solver
    .Method "Hexahedral TLM"
    .StimulationPort "Plane wave"
    .StimulationMode "1"
    .SteadyStateLimit "-40"
    .MeshAdaption "False"
    .HardwareAcceleration "True"
    .StoreTDResultsInCache "False"
    .RunDiscretizerOnly "False"
    .FullDeembedding "False"
    .SuperimposePLWExcitation "False"
    .UseSensitivityAnalysis "False"
End With""", timeout=600)
    return L


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
    return FF_VBA % (FMON, nt, npp - 1, FF_STEP, FF_STEP, FMON * 1e9,
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--total", type=int, default=100)
    ap.add_argument("--root", default=r"D:\dataset_ess10")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--minstep", type=float, default=0.30)
    ap.add_argument("--seed0", type=int, default=77000)
    args = ap.parse_args()

    global ROOT
    ROOT = args.root
    codes_dir = os.path.join(ROOT, "codes")
    results = os.path.join(ROOT, "results")
    ffd = os.path.join(results, "ff")
    work = os.path.join(ROOT, "work")
    for d in (ROOT, codes_dir, results, ffd, work):
        os.makedirs(d, exist_ok=True)

    macro = args.n // 2
    L = args.n * P
    lam = C0 / (FMON * 1e9) * 1e3
    plate_db = 10 * np.log10(4 * np.pi * (L * 1e-3) ** 4 / (lam * 1e-3) ** 2)
    log("ESS array %d x %d sub-cells (%d x %d macro), %.0f mm, TLM default mesh"
        % (args.n, args.n, macro, macro, L))
    log("plate reference sigma = %.2f dBsm" % plate_db)

    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)

    times = []
    rng = random.Random(args.seed0 + args.n)
    for i in range(args.total):
        res_path = os.path.join(results, "res_%04d.json" % i)
        if os.path.isfile(res_path):
            continue
        code = [[rng.randint(0, 1) for _ in range(macro)] for _ in range(macro)]
        ff_path = os.path.join(ffd, "ff_%04d.txt" % i)
        ff_tmp = ff_path + ".tmp"
        prj = None
        t0 = time.time()
        try:
            prj = de.new_mws()
            time.sleep(0.5)
            m = prj.model3d
            build_case(prj, args.n, code, args.minstep)
            t_mesh = time.time()
            m.add_to_history("mesh", "Mesh.Update", timeout=1800)
            mesh_s = time.time() - t_mesh
            cells = m.Mesh.GetNumberOfMeshCells()
            t_solve = time.time()
            m.run_solver()
            solve_s = time.time() - t_solve
            m._execute_vba_code(ff_vba(ff_tmp))
            spec, mean_far, mx = analyse(ff_tmp)
            os.replace(ff_tmp, ff_path)
            rec = dict(index=i, n=args.n, macro=macro,
                       code="".join("".join(str(b) for b in row) for row in code),
                       freq_ghz=FMON, ff_step=FF_STEP, cells=cells,
                       specular_dbsm=round(spec, 3),
                       reduction_db=round(spec - plate_db, 3),
                       mean_far_dbsm=round(mean_far, 3), max_dbsm=round(mx, 3),
                       mesh_s=round(mesh_s, 1), solve_s=round(solve_s, 1),
                       wall_s=round(time.time() - t0, 1), mem_pct=mem_load(),
                       done=time.strftime("%Y-%m-%d %H:%M:%S"))
            atomic_write(res_path, json.dumps(rec) + "\n")
            with open(os.path.join(ROOT, "progress.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            atomic_write(os.path.join(codes_dir, "code_%04d.txt" % i),
                         "# index %d  n=%d  macro=%d\n%s"
                         % (i, args.n, macro, "\n".join("".join(str(b) for b in r) for r in code)))
            times = (times + [time.time() - t0])[-10:]
            avg = sum(times) / len(times)
            log("case %04d  cells %d  spec %6.2f dBsm  red %6.2f dB  mesh %.0fs solve %.0fs "
                "(avg %.0fs, ~%.1f h left)"
                % (i, cells, spec, spec - plate_db, mesh_s, solve_s, avg,
                   (args.total - i - 1) * avg / 3600.0))
            prj.close()
            prj = None
        except Exception as exc:  # noqa: BLE001
            log("case %04d FAILED after %.0fs: %s" % (i, time.time() - t0, str(exc).replace("\n", " ")[:200]))
            try:
                if prj is not None:
                    prj.close()
            except Exception:
                pass
        if args.once:
            break


if __name__ == "__main__":
    main()
