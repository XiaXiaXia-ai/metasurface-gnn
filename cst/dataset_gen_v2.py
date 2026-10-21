# -*- coding: utf-8 -*-
"""快速验证数据集 v2：布局族 + 复数远场 + 可复现清单。

对齐两份计划文档：
  * 曲面反射型超表面_GNN研究现状与实施计划（步骤 02 / 05 / 06）
  * technical_route_fast_validation（阶段二）

与 v1（dataset_gen.py）的差别：
  1. 阵列规模可配（8 / 10 / 20），网格与背景空间随之缩放；
  2. 布局按"族"生成：random(p) / ramp(theta,phi) / checker / half / uniform；
  3. 导出**复数**远场（幅度 + 相位，two polarisations），而不是只有 dBsm；
  4. 每例写 manifest：layout_id / family / params / bits，按 layout_id 分组建划分。

用法
    python dataset_gen_v2.py --plan                # 只打印样本计划，不碰 CST
    python dataset_gen_v2.py --n 8 --limit 5      # 生成 5 例
    python dataset_gen_v2.py --status
"""
import argparse
import json
import os
import random
import sys
import time

import numpy as np

P = 14.0                 # unit-cell period (mm)
SUB_H = 1.5              # substrate thickness (mm)
R0, R1 = 4.7, 2.0        # bit 0 / bit 1 patch radius (mm)
FMIN, FMAX, FMON = 9.0, 11.0, 10.0
BG_SPACE = 15.0          # background surrounding space (mm), validated for 20x20
FF_STEP = 2.0            # far-field angular step (deg)
ROOT = r"D:\dataset_v2"
CST_LIB = r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries"


# ------------------------------------------------------------------ sample plan
def plan(n_side=8, seed=20261021):
    """Deterministic sample plan: list of dicts with family + params."""
    rng = random.Random(seed)
    out = []

    def add(family, count, **params):
        for k in range(count):
            out.append(dict(family=family, idx=len(out), **params, sub=k))

    # 布局族配比（--plan 可核对）
    add("random", 60, p=0.5)
    add("random", 20, p=0.3)
    add("random", 20, p=0.7)
    add("ramp", 16)          # theta/phi 由 idx 展开
    add("checker", 8, block=2)
    add("half", 8)
    add("uniform", 8)

    for i, s in enumerate(out):
        s["layout_id"] = "L%03d" % i
        if s["family"] == "ramp":
            ang = (5, 10, 15, 20, 25, 30, 35, 40)
            s["theta"] = ang[s["sub"] % len(ang)]
            s["phi"] = 0.0 if (s["sub"] // len(ang)) % 2 == 0 else 90.0
        if s["family"] == "uniform":
            s["state"] = s["sub"] % 2
        s["seed"] = rng.randrange(1 << 30)
        del s["sub"]
    return out


def make_code(spec, n_side):
    """Return (n_side x n_side) 0/1 array for one plan entry."""
    N = n_side
    rng = np.random.default_rng(spec["seed"])
    fam = spec["family"]
    if fam == "random":
        return (rng.random((N, N)) < spec["p"]).astype(int)
    if fam == "uniform":
        return np.full((N, N), spec.get("state", 0), dtype=int)
    if fam == "checker":
        b = spec.get("block", 2)
        i = np.arange(N) // b
        return ((i[:, None] + i[None, :]) % 2).astype(int)
    if fam == "half":
        return (np.arange(N)[None, :] >= N // 2).astype(int) * np.ones((N, 1), int)
    if fam == "ramp":
        lam = 29.9792458
        k = 2 * np.pi / lam
        x = (np.arange(N) - (N - 1) / 2.0) * P
        X, Y = np.meshgrid(x, x, indexing="ij")
        t, ph = np.radians(spec["theta"]), np.radians(spec["phi"])
        psi = k * (X * np.sin(t) * np.cos(ph) + Y * np.sin(t) * np.sin(ph))
        return (np.cos(psi) < 0).astype(int)
    raise ValueError(fam)


# ----------------------------------------------------------------------- CST VBA
def build_vba(n_side, bits):
    half = n_side * P / 2.0
    L = """With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
    .SetUnit "Time", "ns"
End With
Solver.FrequencyRange "%g", "%g"
With Boundary
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
End With
With Background
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
With Material
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
End With
With Brick
    .Reset
    .Name "substrate"
    .Component "Array"
    .Material "material1"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "%g"
    .Create
End With
With Brick
    .Reset
    .Name "ground"
    .Component "Array"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "0"
    .Create
End With
""" % (FMIN, FMAX, (FMIN + FMAX) / 2.0,
       BG_SPACE, BG_SPACE, BG_SPACE, BG_SPACE, BG_SPACE, BG_SPACE,
       -half, half, -half, half, SUB_H,
       -half, half, -half, half)

    patches = []
    for m in range(n_side):
        for n in range(n_side):
            x = (m - (n_side - 1) / 2.0) * P
            y = (n - (n_side - 1) / 2.0) * P
            r = R1 if bits[m][n] else R0
            patches.append("""With Cylinder
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

    tail = """With PlaneWave
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
End With
With Monitor
    .Reset
    .Name "farfield (f=%g)"
    .Domain "Frequency"
    .FieldType "Farfield"
    .MonitorValue "%g"
    .UseSubvolume "False"
    .ExportFarfieldSource "False"
    .Create
End With
ChangeSolverType "HF Time Domain"
With Solver
    .Method "Hexahedral"
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
End With
""" % (FMON, FMON, FMON)
    return L + "".join(patches) + tail


FF_VBA = r'''Sub Main()
    Dim it, ip, i, nt, np_
    Dim a1, a2, a3, a4
    nt = %d : np_ = %d
    SelectTreeItem ("Farfields\\farfield (f=%g) [pw]")
    FarfieldPlot.Reset
    For it = 0 To nt
        For ip = 0 To np_ - 1
            FarfieldPlot.AddListEvaluationPoint it*%g, ip*%g, 0, "spherical", "frequency", %.0f
        Next ip
    Next it
    FarfieldPlot.CalculateList ""
    a1 = FarfieldPlot.GetList("Spherical linear theta abs")
    a2 = FarfieldPlot.GetList("Spherical linear theta phase")
    a3 = FarfieldPlot.GetList("Spherical linear phi abs")
    a4 = FarfieldPlot.GetList("Spherical linear phi phase")
    Open "%s" For Output As #1
    For it = 0 To nt
        For ip = 0 To np_ - 1
            i = it * np_ + ip
            Print #1, (it*%g) & " " & (ip*%g) & " " & a1(i) & " " & a2(i) & " " & a3(i) & " " & a4(i)
        Next ip
    Next it
    Close #1
End Sub'''


def ff_vba(path):
    nt = int(round(90.0 / FF_STEP))
    npp = int(round(360.0 / FF_STEP))
    return FF_VBA % (nt, npp, FMON, FF_STEP, FF_STEP, FMON * 1e9, path, FF_STEP, FF_STEP)


def analyse(path):
    d = np.loadtxt(path, encoding="utf-8", errors="replace")
    th = d[:, 0]
    rcs = 10.0 * np.log10(10 ** (d[:, 2] / 10.0) + 10 ** (d[:, 4] / 10.0))
    spec = float(rcs[np.argmin(np.abs(th - 0.0))])
    far = th >= 10.0
    mean_far = float(10.0 * np.log10(np.mean(10 ** (rcs[far] / 10.0))))
    return spec, mean_far, float(rcs.max())


# ------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    samples = plan(args.n)
    base = os.path.join(ROOT, "n%d" % args.n)
    codes_dir = os.path.join(base, "codes")
    res_dir = os.path.join(base, "results")
    ff_dir = os.path.join(res_dir, "ff")

    if args.plan or args.dry_run:
        fam = {}
        for s in samples:
            fam[s["family"]] = fam.get(s["family"], 0) + 1
        print("n=%d  样本数=%d  布局族=%s" % (args.n, len(samples), fam))
        for s in samples[:6]:
            bits = make_code(s, args.n)
            print("  %s %-8s %s  ones=%2d" % (s["layout_id"], s["family"],
                                              "".join(str(b) for b in bits.ravel()), bits.sum()))
        if args.dry_run:
            vba = build_vba(args.n, make_code(samples[0], args.n))
            print("\nVBA chars=%d  patches=%d  ff_vba chars=%d"
                  % (len(vba), vba.count("With Cylinder"), len(ff_vba(r"X:\\ff.txt"))))
        return

    for d in (codes_dir, res_dir, ff_dir):
        os.makedirs(d, exist_ok=True)
    if args.status:
        n = sum(1 for _ in os.listdir(res_dir) if _.startswith("res_") and _.endswith(".json"))
        print("finished %d / %d" % (n, len(samples)))
        return

    sys.path.insert(0, CST_LIB)
    import cst.interface  # noqa: E402
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    try:
        de.set_quiet_mode(True)
    except Exception:
        pass

    done = 0
    for s in samples:
        if args.limit and done >= args.limit:
            break
        res_path = os.path.join(res_dir, "res_%03d.json" % s["idx"])
        if os.path.isfile(res_path):
            continue
        bits = make_code(s, args.n)
        ff_path = os.path.join(ff_dir, "ff_%03d.txt" % s["idx"])
        prj = None
        t0 = time.time()
        try:
            prj = de.new_mws()
            time.sleep(0.5)
            m = prj.model3d
            m.add_to_history("build model", build_vba(args.n, bits), timeout=900)
            m.run_solver()
            m._execute_vba_code(ff_vba(ff_path))
            spec, mean_far, mx = analyse(ff_path)
            rec = dict(idx=s["idx"], layout_id=s["layout_id"], family=s["family"],
                       n_side=args.n, freq_ghz=FMON, ff_step=FF_STEP,
                       bits="".join(str(b) for b in bits.ravel()),
                       seed=s["seed"], specular_dbsm=round(spec, 3),
                       mean_far_dbsm=round(mean_far, 3), max_dbsm=round(mx, 3),
                       wall_s=round(time.time() - t0, 1),
                       done=time.strftime("%Y-%m-%d %H:%M:%S"))
            tmp = res_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            os.replace(tmp, res_path)
            print("[%03d] %-8s ones=%2d  spec %6.2f dBsm  %.0fs"
                  % (s["idx"], s["family"], bits.sum(), spec, time.time() - t0), flush=True)
            done += 1
        except Exception as exc:  # noqa: BLE001
            print("[%03d] FAILED %s" % (s["idx"], str(exc).replace("\n", " ")[:140]), flush=True)
        finally:
            if prj is not None:
                try:
                    prj.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
