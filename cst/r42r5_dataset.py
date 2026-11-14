# -*- coding: utf-8 -*-
"""r=4.2 / r=5 coding-array dataset: 8x8 cells (2x2 macro -> 4x4), TLM solver.

Unit cell (same geometry as build_coding_array.py / r47_wanggemore.cst):
    period 14 mm, material1 (er=2.65, tanD=0.0013) h=1.5 mm, PEC ground at z=0,
    circular PEC patch at z=1.5:
        r = 4.2 mm -> phase  +90.8 deg   (bit 1)
        r = 5.0 mm -> phase  -91.6 deg   (bit 0)
    phase difference ~182 deg.

Differences vs build_coding_array.py (deliberate, for the record):
    N 20 -> 8,  BLOCK stays 2 (4x4 macro),  R0 4.7 -> 5.0,  R1 2.0 -> 4.2,
    solver TD "Hexahedral" -> "Hexahedral TLM",
    added one 2D E-field monitor at z=2 mm for the near-field map.

Usage:
    python r42r5_dataset.py --total 1000 --root D:\\dataset_r42r5 [--once] [--start 0]
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

P = 14.0
N = 8             # sub-cells per side; override with --n (12 -> 6x6 macro)
BLOCK = 2
NB = N // BLOCK
R0 = 5.0          # bit 0 -> -91.6 deg
R1 = 4.2          # bit 1 -> +90.8 deg
SUB_H = 1.5
FMIN, FMAX = 9.0, 11.0
FMON = 10.0
BG = 15.0
FF_STEP = 2.0
C0 = 299.792458
L = N * P
half = L / 2.0

ROOT = None


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(ROOT, "progress.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def mem_load():
    try:
        import subprocess
        out = subprocess.run(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/format:list"],
                             capture_output=True, text=True, timeout=10).stdout
        d = dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)
        return int(100 * (1 - float(d["FreePhysicalMemory"]) / float(d["TotalVisibleMemorySize"])))
    except Exception:
        return -1


def patches_vba(code):
    out = []
    for m in range(N):
        for n in range(N):
            x = (m - (N - 1) / 2.0) * P
            y = (n - (N - 1) / 2.0) * P
            r = R1 if code[m][n] else R0
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
""" % (m, n, r, SUB_H, SUB_H, x, y))
    return "".join(out)


def build_case(prj, code):
    m = prj.model3d
    blocks = [
        ("units", """With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
    .SetUnit "Time", "ns"
End With"""),
        ("freq", 'Solver.FrequencyRange "%g", "%g"' % (FMIN, FMAX)),
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
    .MinimumDistanceType "Fraction"
    .MinimumDistancePerWavelengthNewMeshEngine "4"
    .MinimumDistanceReferenceFrequencyType "Center"
    .FrequencyForMinimumDistance "%g"
End With""" % ((FMIN + FMAX) / 2.0,)),
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
        ("material", """With Material
    .Reset
    .Name "material1"
    .Folder ""
    .FrqType "all"
    .Type "Normal"
    .MaterialUnit "Frequency", "GHz"
    .MaterialUnit "Geometry", "mm"
    .MaterialUnit "Time", "ns"
    .Epsilon "2.65"
    .Mu "1"
    .Sigma "0.0"
    .TanD "0.0013"
    .TanDFreq "0.0"
    .TanDGiven "True"
    .TanDModel "ConstTanD"
    .Colour "0", "1", "1"
    .Create
End With"""),
        ("substrate", """With Brick
    .Reset
    .Name "substrate"
    .Component "Array"
    .Material "material1"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "%g"
    .Create
End With""" % (-half, half, -half, half, SUB_H)),
        ("ground", """With Brick
    .Reset
    .Name "ground"
    .Component "Array"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "0"
    .Create
End With""" % (-half, half, -half, half)),
        ("patches", patches_vba(code)),
        ("plane wave", """With PlaneWave
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
End With""" % FMON),
        ("farfield monitor", """With Monitor
    .Reset
    .Name "farfield (f=%g)"
    .Domain "Frequency"
    .FieldType "Farfield"
    .MonitorValue "%g"
    .UseSubvolume "False"
    .ExportFarfieldSource "False"
    .Create
End With""" % (FMON, FMON)),
        ("solver type", 'ChangeSolverType "HF Time Domain"'),
        ("solver TLM", """With Solver
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
End With"""),
        ("mesh type", """With Mesh
    .MeshType "HexahedralTLM"
End With"""),
    ]
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=600)


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


def analyse_ff(path):
    d = np.loadtxt(path)
    th = d[:, 0]
    rcs = 10.0 * np.log10(10 ** (d[:, 2] / 10.0) + 10 ** (d[:, 3] / 10.0))
    spec = float(rcs[np.argmin(np.abs(th - 0.0))])
    far = th >= 10.0
    mean_far = float(10.0 * np.log10(np.mean(10 ** (rcs[far] / 10.0))))
    return spec, mean_far, float(rcs.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--total", type=int, default=1000)
    ap.add_argument("--root", default=r"D:\dataset_r42r5")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--seed0", type=int, default=99100)
    args = ap.parse_args()

    global ROOT, N, NB, L, half
    N = args.n
    NB = N // BLOCK
    L = N * P
    half = L / 2.0
    ROOT = args.root
    codes_dir = os.path.join(ROOT, "codes")
    results = os.path.join(ROOT, "results")
    ffd = os.path.join(results, "ff")
    for d in (ROOT, codes_dir, results, ffd):
        os.makedirs(d, exist_ok=True)

    lam = C0 / FMON
    plate_db = 10 * np.log10(4 * np.pi * (L * 1e-3) ** 4 / (lam * 1e-3) ** 2)
    log("r4.2/r5 coding array: %d x %d cells (block %d -> %dx%d macro), %.0f mm, TLM"
        % (N, N, BLOCK, NB, NB, L))
    log("R0=%.1f (-91.6deg)  R1=%.1f (+90.8deg)  plate sigma=%.2f dBsm" % (R0, R1, plate_db))

    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)

    # keep the DesignEnvironment controllable: never leave more than 1 project open
    def trim_projects(keep=0):
        try:
            opened = de.get_open_projects()
            while len(opened) > keep:
                try:
                    opened[-1].close()
                except Exception:
                    pass
                opened = de.get_open_projects()
        except Exception:
            pass

    trim_projects(keep=0)

    times = []
    for i in range(args.start, args.total):
        res_path = os.path.join(results, "res_%04d.json" % i)
        if os.path.isfile(res_path):
            continue
        seed_i = args.seed0 + i
        rng = random.Random(seed_i)
        bits = [[rng.randint(0, 1) for _ in range(NB)] for _ in range(NB)]
        code = [[bits[m // BLOCK][n // BLOCK] for n in range(N)] for m in range(N)]
        ff_path = os.path.join(ffd, "ff_%04d.txt" % i)
        ff_tmp = ff_path + ".tmp"
        prj = None
        t0 = time.time()
        try:
            trim_projects(keep=0)
            prj = de.new_mws()
            time.sleep(0.5)
            build_case(prj, code)
            t_mesh = time.time()
            prj.model3d.add_to_history("mesh", "Mesh.Update", timeout=1800)
            mesh_s = time.time() - t_mesh
            cells = prj.model3d.Mesh.GetNumberOfMeshCells()
            t_solve = time.time()
            prj.model3d.run_solver()
            solve_s = time.time() - t_solve
            prj.model3d._execute_vba_code(ff_vba(ff_tmp))
            spec, mean_far, mx = analyse_ff(ff_tmp)
            os.replace(ff_tmp, ff_path)
            rec = dict(index=i, n=N, block=BLOCK, r0=R0, r1=R1,
                       code="".join("".join(str(b) for b in r) for r in bits),
                       cells=cells, specular_dbsm=round(spec, 3),
                       reduction_db=round(spec - plate_db, 3),
                       mean_far_dbsm=round(mean_far, 3), max_dbsm=round(mx, 3),
                       mesh_s=round(mesh_s, 1),
                       solve_s=round(solve_s, 1), wall_s=round(time.time() - t0, 1),
                       mem_pct=mem_load(), done=time.strftime("%Y-%m-%d %H:%M:%S"))
            atomic_write(res_path, json.dumps(rec) + "\n")
            with open(os.path.join(ROOT, "progress.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            atomic_write(os.path.join(codes_dir, "code_%04d.txt" % i),
                         "# index %d  seed %d  r0=%.1f r1=%.1f\n%s"
                         % (i, seed_i, R0, R1, "\n".join("".join(str(b) for b in r) for r in bits)))
            times = (times + [time.time() - t0])[-10:]
            avg = sum(times) / len(times)
            log("case %04d  cells %d  spec %6.2f  red %6.2f  mesh %.0fs solve %.0fs "
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
