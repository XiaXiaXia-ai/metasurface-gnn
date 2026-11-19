# -*- coding: utf-8 -*-
"""新单元 r = 4.2 / 5.0 的 8x8 圆柱面（R = 200 mm）编码阵列：VBA 宏生成器。

几何沿用 `cst/build_cylinder_csg.py` 里**已经跑通**的 CSG 做法
（圆柱壳 + 逐单元 tube ∩ box ∩ cutter，不用 Bend），只改三件事：

1. 单元半径换成新单元（bit0 = 5.0 mm、bit1 = 4.2 mm）；
2. 求解器换成 TLM（`ChangeSolverType "HF TLM"`，排在建模之后、求解之前）；
3. 补上 6 列复数远场导出（8280 方向）和 build_meta.json（含贴片半径）。

本模块**不启动 CST**：只把完整 VBA 写成 .bas，用户在 CST 里
File -> Macro -> Load VBA 手动跑。宏里的开关 RUN_SOLVER / RUN_EXPORT /
RUN_SELFCHECK 决定"只建模 / 建模后求解 / 求解后导出远场 / 顺手核对贴片体积"。

用法
----
    # 目标算例（演示码 0000010010100111，来自新数据集 case 0000）
    python cst/r42r5_curved.py --dry-run --out cst/out/r42r5_R200_n8.bas

    # 相位门最便宜的两个算例（各 1 例，两个共约 6 min）
    python cst/r42r5_curved.py --dry-run --code uniform0 --out cst/out/r42r5_R200_n8_u0.bas
    python cst/r42r5_curved.py --dry-run --code uniform1 --out cst/out/r42r5_R200_n8_u1.bas

    # 只改曲率/码，其它全用默认
    python cst/r42r5_curved.py --dry-run --R 300 --code 1010101010101010 --out cst/out/r42r5_R300_n8.bas

生成物与 .bas 同目录：`<stem>_build_meta.json`（R、码、逐单元贴片半径、静态自检结果）。

契约（与本仓库其它生成器一致）
------------------------------
* 宏整体包在 `Sub Main() ... End Sub` 里（TLM 的硬性要求）；
* 对象命名沿用 `Array:substrate` / `Array:ground` / `Array:patch_MM_NN`，
  临时体 `tmp_box` / `tmp_cut` 每次布尔后被吃掉（最终 2 + 64 = 66 个对象）；
* 码的约定与 `gnn/msgnn/data/dataset.py` 一致：nbit x nbit 宏码**行主序**，
  `bits[m][n]`（m 沿 x、n 沿 y），再按 block 上采样；
* .bas 是**纯 ASCII**（CST 的 VBA 解析器按 ANSI 读文件，中文注释会乱码）。

凡是不能在没有 CST 的情况下确认的（例如曲面上的 CSG 布尔是否真的干净），
在 docs/reports/2026-11-13_r42r5_curved_model_spec.md 里一律标 "需用户实跑验证"。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

# ------------------------------------------------------------------ 参数块
N = 8                       # 每边单元数（8x8 = 64 个单元）
R = 200.0                   # 圆柱半径, mm（凹向 +z：x = R sin(u/R), z = R(1-cos(u/R))）
P = 14.0                    # 周期, mm（口径 N*P = 112 mm）
SUB_H = 1.5                 # 基板厚度, mm
ER = 2.65                   # 基板 εr
TAN_D = 0.0013              # 基板 tanδ
R0, R1 = 5.0, 4.2           # 贴片半径, mm：bit0 -> R0, bit1 -> R1（注意 bit1 更小）
CODE = "0000010010100111"   # 16 位宏码（4x4, block=2, 行主序），新数据集 case 0000
BG = 15.0                   # 背景空间, mm（六面 open）

BLOCK = 2                   # 一个码位覆盖 block x block 个单元
PATCH_T = 0.2               # 贴片金属壳厚度（径向）, mm
EMBED = 0.02                # 向基板嵌入的径向重叠, mm（保证 CSG 接触，不是 lift）
FMIN, FMAX, FMON = 9.0, 11.0, 10.0   # GHz
FF_STEP = 2.0               # 远场角度步进, deg -> 46 x 180 = 8280 方向
MESH_STEPS = 20             # StepsPerWaveNear/Far（与 2026-11-12 的 TLM 参考工程同设置）
ARC_SEG = 64                # 基板 Extrude 的弧段数
GROUND_SEG = 96             # 地板 Loft 的弧段数
SOLVER = "tlm"              # "tlm"（默认，唯一建议）| "fit"（只用于复现症状）

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "out", "r42r5_R200_n8.bas")


def _fmt(x: float) -> str:
    return "%.6f" % float(x)


# ------------------------------------------------------------------ 码
def expand_code(code, n_side: int = N, block: int = BLOCK):
    """把 'uniform0' / 'uniform1' / 二进制串展开成 n_side x n_side 的 0/1。

    返回 (bits, macro, label)：bits[m][n]（m 沿 x），macro 是 nbit x nbit 宏码。
    """
    nbit = n_side // block
    if nbit * block != n_side:
        raise ValueError("n_side=%d 不能被 block=%d 整除" % (n_side, block))
    s = str(code).strip().lower()
    if s in ("uniform0", "uniform", "u0", "zeros", "all0"):
        macro = [[0] * nbit for _ in range(nbit)]
        label = "uniform0"
    elif s in ("uniform1", "u1", "ones", "all1"):
        macro = [[1] * nbit for _ in range(nbit)]
        label = "uniform1"
    else:
        s2 = "".join(ch for ch in s if ch in "01")
        if len(s2) != nbit * nbit:
            raise ValueError("码 %r 不是 %d 位二进制串（%dx%d 宏码）"
                             % (code, nbit * nbit, nbit, nbit))
        macro = [[int(s2[i * nbit + j]) for j in range(nbit)] for i in range(nbit)]
        label = s2
    bits = [[macro[m // block][nn // block] for nn in range(n_side)]
            for m in range(n_side)]
    return bits, macro, label


def code_to_str(bits) -> str:
    return "".join(str(v) for row in bits for v in row)


def cells(n_side: int = N, period: float = P, radius: float = R):
    """单元中心的解析几何：u 是沿弧长坐标，θ = u/R。"""
    out = []
    for m in range(n_side):
        u = (m - (n_side - 1) / 2.0) * period
        th = u / radius
        out.append({
            "m": m,
            "u_mm": u,
            "theta_deg": math.degrees(th),
            "x_mm": radius * math.sin(th),
            "z_mm": radius * (1.0 - math.cos(th)),
            "normal": (-math.sin(th), 0.0, math.cos(th)),
            "tangent": (math.cos(th), 0.0, math.sin(th)),
        })
    return out


# ------------------------------------------------------------------ 几何 VBA
def arc_profile(inner_r: float, outer_r: float, th_max: float, segments: int,
                axis_r: float):
    pts = []
    for i in range(segments + 1):
        th = -th_max + 2.0 * th_max * i / float(segments)
        pts.append((outer_r * math.sin(th), axis_r - outer_r * math.cos(th)))
    for i in range(segments, -1, -1):
        th = -th_max + 2.0 * th_max * i / float(segments)
        pts.append((inner_r * math.sin(th), axis_r - inner_r * math.cos(th)))
    return pts


def extrude_vba(name, material, inner_r, outer_r, th_max, segments, length,
                axis_r, indent="    "):
    """基板：x-z 平面上的圆环扇区折线，沿 y 拉 length。"""
    pts = arc_profile(inner_r, outer_r, th_max, segments, axis_r)
    x0, z0 = pts[0]
    L = [indent + "With Extrude",
         indent + "    .Reset",
         indent + '    .Name "%s"' % name,
         indent + '    .Component "Array"',
         indent + '    .Material "%s"' % material,
         indent + '    .Mode "Pointlist"',
         indent + '    .Height "%s"' % _fmt(length),
         indent + '    .Origin "0", "%s", "0"' % _fmt(-length / 2.0),
         indent + '    .Uvector "1", "0", "0"',
         indent + '    .Vvector "0", "0", "1"',
         indent + '    .Point "%s", "%s"' % (_fmt(x0), _fmt(z0))]
    for x, z in pts[1:]:
        L.append(indent + '    .LineTo "%s", "%s"' % (_fmt(x), _fmt(z)))
    L.append(indent + '    .LineTo "%s", "%s"' % (_fmt(x0), _fmt(z0)))
    L += [indent + "    .Create", indent + "End With"]
    return "\n".join(L)


def ground_sheet_vba(name, radius_sheet, th_max, segments, length, axis_r,
                     indent="    "):
    """地板：0 mm 零厚度 PEC 圆柱面扇区（Solid False 的 Loft）。"""
    pts = []
    for i in range(segments + 1):
        th = -th_max + 2.0 * th_max * i / float(segments)
        pts.append((radius_sheet * math.sin(th),
                    axis_r - radius_sheet * math.cos(th)))
    L = [indent + 'Curve.NewCurve "ground_curve"']
    for item, y in (("ground_arc_a", -length / 2.0),
                    ("ground_arc_b", length / 2.0)):
        L += [indent + "With Polygon3D",
              indent + "    .Reset",
              indent + '    .Name "%s"' % item,
              indent + '    .Curve "ground_curve"']
        for x, z in pts:
            L.append(indent + '    .Point "%s", "%s", "%s"'
                     % (_fmt(x), _fmt(y), _fmt(z)))
        L += [indent + "    .Create", indent + "End With"]
    L += [indent + "With LoftCurves",
          indent + "    .Reset",
          indent + '    .Name "%s"' % name,
          indent + '    .Component "Array"',
          indent + '    .Material "PEC"',
          indent + '    .Solid "False"',
          indent + '    .MinimizeTwist "True"',
          indent + '    .AddCurve "ground_curve:ground_arc_a"',
          indent + '    .AddCurve "ground_curve:ground_arc_b"',
          indent + "    .Create",
          indent + "End With"]
    return "\n".join(L)


# ------------------------------------------------------------------ 主生成
def build_vba(n_side: int = N, radius: float = R, period: float = P,
              sub_h: float = SUB_H, er: float = ER, tan_d: float = TAN_D,
              r0: float = R0, r1: float = R1, code=CODE, block: int = BLOCK,
              bg: float = BG, patch_t: float = PATCH_T, embed: float = EMBED,
              fmin: float = FMIN, fmax: float = FMAX, fmon: float = FMON,
              ff_step: float = FF_STEP, mesh_steps: int = MESH_STEPS,
              arc_seg: int = ARC_SEG, ground_seg: int = GROUND_SEG,
              solver: str = SOLVER, run_solver: bool = False,
              run_export: bool = False, run_selfcheck: bool = True,
              ff_out: str = "", vol_out: str = "") -> str:
    """返回**完整**的 VBA 宏字符串（含 Sub Main / End Sub）。"""
    if solver not in ("tlm", "fit"):
        raise ValueError("solver must be 'tlm' or 'fit'")
    if max(r0, r1) + 1.0 >= period / 2.0:
        raise ValueError("patch radius %.2f + 1 mm margin exceeds P/2 = %.2f; "
                         "the CSG clipping boxes of adjacent cells would overlap"
                         % (max(r0, r1), period / 2.0))
    bits, macro, label = expand_code(code, n_side, block)
    nbit = n_side // block
    L = n_side * period
    half = L / 2.0
    th_max = half / radius
    cs = cells(n_side, period, radius)
    nt = int(round(90.0 / ff_step))
    nphi = int(round(360.0 / ff_step))
    r_open, r_close = radius + embed, radius + embed - patch_t
    g_rad = radius + sub_h
    if not ff_out:
        ff_out = os.path.join(HERE, "out", "ff_%s.txt" % label)
    if not vol_out:
        vol_out = os.path.join(HERE, "out", "selfcheck_%s.txt" % label)

    A = []
    add = A.append
    add("'=====================================================================")
    add("'  r42r5 curved array  --  R=%.1f mm  %dx%d  block=%d  %s"
        % (radius, n_side, n_side, block, solver.upper()))
    add("'  substrate %.2f mm  er=%.2f  tand=%.4f   ground 0 mm PEC @ R+%.2f"
        % (sub_h, er, tan_d, sub_h))
    add("'  patch radii: bit0 -> %.2f mm, bit1 -> %.2f mm   (no lift)"
        % (r0, r1))
    add("'  code (%d bits, row-major): %s   ones=%d/%d"
        % (nbit * nbit, label, sum(sum(row) for row in bits), n_side * n_side))
    add("'  generated by cst/r42r5_curved.py")
    add("'")
    add("'  HOW TO RUN")
    add("'    1. CST Studio Suite -> new, empty Microwave & RF project")
    add("'    2. File -> Macro -> Load VBA ... -> this file -> Open (answer Yes)")
    add("'       (same thing under Home -> Macros -> Load VBA)")
    add("'    3. the macro builds the model and sets solver = TLM")
    add("'    4. if RUN_SOLVER = False: Home -> Solver -> Time Domain Solver")
    add("'    5. results: 1D/2D Results -> Farfields -> farfield (f=%g) [pw]" % fmon)
    add("'")
    add("'  WARNING: run this ONCE in a FRESH project. Re-running it in the same")
    add("'           project duplicates substrate / ground / patch objects.")
    add("'=====================================================================")
    add("Sub Main()")
    add("")
    add("    ' ---------------- switches -------------------------------------")
    add("    Dim RUN_SOLVER As Boolean")
    add("    Dim RUN_EXPORT As Boolean")
    add("    Dim RUN_SELFCHECK As Boolean")
    add("    Dim FF_OUT As String")
    add("    Dim VOL_OUT As String")
    add("    RUN_SOLVER = %s" % ("True" if run_solver else "False"))
    add("    RUN_EXPORT = %s" % ("True" if run_export else "False"))
    add("    RUN_SELFCHECK = %s" % ("True" if run_selfcheck else "False"))
    add('    FF_OUT = "%s"' % ff_out)
    add('    VOL_OUT = "%s"' % vol_out)
    add("")
    add("    ' ---------------- units / frequency range ----------------------")
    add("    With Units")
    add('        .SetUnit "Length", "mm"')
    add('        .SetUnit "Frequency", "GHz"')
    add('        .SetUnit "Time", "ns"')
    add("    End With")
    add('    Solver.FrequencyRange "%g", "%g"' % (fmin, fmax))
    add("")
    add("    ' ---------------- material (substrate) -------------------------")
    add("    With Material")
    add("        .Reset")
    add('        .Name "material1"')
    add('        .Folder ""')
    add('        .FrqType "all"')
    add('        .Type "Normal"')
    add('        .MaterialUnit "Frequency", "GHz"')
    add('        .MaterialUnit "Geometry", "mm"')
    add('        .MaterialUnit "Time", "ns"')
    add('        .Epsilon "%g"' % er)
    add('        .Mu "1"')
    add('        .Sigma "0.0"')
    add('        .TanD "%g"' % tan_d)
    add('        .TanDFreq "0.0"')
    add('        .TanDGiven "True"')
    add('        .TanDModel "ConstTanD"')
    add('        .Colour "0", "1", "1"')
    add("        .Create")
    add("    End With")
    add("")
    add("    ' ---------------- boundary: all six sides open -----------------")
    add("    With Boundary")
    add('        .Xmin "expanded open"')
    add('        .Xmax "expanded open"')
    add('        .Ymin "expanded open"')
    add('        .Ymax "expanded open"')
    add('        .Zmin "expanded open"')
    add('        .Zmax "expanded open"')
    add('        .Xsymmetry "none"')
    add('        .Ysymmetry "none"')
    add('        .Zsymmetry "none"')
    add('        .MinimumDistanceType "Fraction"')
    add('        .MinimumDistancePerWavelengthNewMeshEngine "4"')
    add('        .MinimumDistanceReferenceFrequencyType "Center"')
    add('        .FrequencyForMinimumDistance "%g"' % ((fmin + fmax) / 2.0))
    add("    End With")
    add("")
    add("    ' ---------------- background -----------------------------------")
    add("    With Background")
    add("        .ResetBackground")
    add('        .Type "Normal"')
    add('        .Epsilon "1.0"')
    add('        .Mu "1.0"')
    for key in ("XminSpace", "XmaxSpace", "YminSpace", "YmaxSpace",
                "ZminSpace", "ZmaxSpace"):
        add('        .%s "%g"' % (key, bg))
    add("    End With")
    add("")
    add("    ' ---------------- substrate: cylindrical shell sector R .. R+h --")
    add("    '   (arc polyline in x-z, extruded along y; concave towards +z)")
    add(extrude_vba("substrate", "material1", radius, radius + sub_h, th_max,
                    arc_seg, L, radius))
    add("")
    add("    ' ---------------- ground: 0 mm zero-thickness PEC @ R+%.2f ------" % sub_h)
    add(ground_sheet_vba("ground", g_rad, th_max, ground_seg, L, radius))
    add("")
    add("    ' ---------------- %d patches (curved discs, r = %.2f / %.2f) ------"
        % (n_side * n_side, r0, r1))
    for mi in range(n_side):
        for ni in range(n_side):
            c = cs[mi]
            cc = cs[ni]          # 2026-11-13 fix: the column index sets y
            x, y, z = c["x_mm"], cc["u_mm"], c["z_mm"]
            nx, nz = c["normal"][0], c["normal"][2]
            tx, tz = c["tangent"][0], c["tangent"][2]
            bit = bits[mi][ni]
            r = r1 if bit else r0
            name = "patch_%02d_%02d" % (mi, ni)
            add("    ' ---- %s : bit=%d  r=%.2f mm" % (name, bit, r))
            add("    With Cylinder")
            add("        .Reset")
            add('        .Name "%s"' % name)
            add('        .Component "Array"')
            add('        .Material "PEC"')
            add('        .Axis "y"')
            add('        .OuterRadius "%s"' % _fmt(r_open))
            add('        .InnerRadius "%s"' % _fmt(r_close))
            add('        .Xcenter "0"')
            add('        .Zcenter "%s"' % _fmt(radius))
            add('        .Yrange "%s", "%s"'
                % (_fmt(y - r - 1.0), _fmt(y + r + 1.0)))
            add('        .Segments "0"')
            add("        .Create")
            add("    End With")
            add("    With Brick")
            add("        .Reset")
            add('        .Name "tmp_box"')
            add('        .Component "Array"')
            add('        .Material "Vacuum"')
            add('        .Xrange "%s", "%s"' % (_fmt(x - r - 1.0), _fmt(x + r + 1.0)))
            add('        .Yrange "%s", "%s"' % (_fmt(y - r - 1.0), _fmt(y + r + 1.0)))
            add('        .Zrange "%s", "%s"' % (_fmt(z - r - 1.0), _fmt(z + r + 1.0)))
            add("        .Create")
            add("    End With")
            add('    Solid.Intersect "Array:%s", "Array:tmp_box"' % name)
            add("    With WCS")
            add('        .SetOrigin "%s", "%s", "%s"' % (_fmt(x), _fmt(y), _fmt(z)))
            add('        .SetNormal "%s", "0", "%s"' % (_fmt(nx), _fmt(nz)))
            add('        .SetUVector "%s", "0", "%s"' % (_fmt(tx), _fmt(tz)))
            add('        .ActivateWCS "local"')
            add("    End With")
            add("    With Cylinder")
            add("        .Reset")
            add('        .Name "tmp_cut"')
            add('        .Component "Array"')
            add('        .Material "Vacuum"')
            add('        .OuterRadius "%s"' % _fmt(r))
            add('        .InnerRadius "0"')
            add('        .Axis "z"')
            add('        .Zrange "-1", "%s"' % _fmt(patch_t + embed + 1.0))
            add('        .Xcenter "0"')
            add('        .Ycenter "0"')
            add('        .Segments "0"')
            add("        .Create")
            add("    End With")
            add('    WCS.ActivateWCS "global"')
            add('    Solid.Intersect "Array:%s", "Array:tmp_cut"' % name)
    add("")
    add("    Plot.ZoomToStructure")
    add("")
    add("    ' ---------------- plane wave: k=(0,0,-1), E=(1,0,0) ------------")
    add("    With PlaneWave")
    add("        .Reset")
    add('        .Normal "0", "0", "-1"')
    add('        .EVector "1", "0", "0"')
    add('        .Polarization "Linear"')
    add('        .ReferenceFrequency "%g"' % fmon)
    add('        .PhaseDifference "0.0"')
    add('        .CircularDirection "Left"')
    add('        .AxialRatio "0.0"')
    add('        .SetUserDecouplingPlane "False"')
    add("        .Store")
    add("    End With")
    add("")
    add("    ' ---------------- far-field monitor ----------------------------")
    add("    With Monitor")
    add("        .Reset")
    add('        .Name "farfield (f=%g)"' % fmon)
    add('        .Domain "Frequency"')
    add('        .FieldType "Farfield"')
    add('        .MonitorValue "%g"' % fmon)
    add('        .UseSubvolume "False"')
    add('        .ExportFarfieldSource "False"')
    add("        .Create")
    add("    End With")
    add("")
    add("    ' ---------------- mesh: set while the default FIT is active; the")
    add("    '   TLM project inherits these settings (same state as the")
    add("    '   2026-11-12 reference project that gave 700 422 cells) -------")
    add("    With MeshSettings")
    add('        .SetMeshType "Hex"')
    add('        .Set "StepsPerWaveNear", "%d"' % int(mesh_steps))
    add('        .Set "StepsPerWaveFar", "%d"' % int(mesh_steps))
    add("    End With")
    add("")
    if solver == "tlm":
        add("    ' ---------------- solver: HF TLM -------------------------------")
        add("    '   MUST come after the geometry and before the solve.")
        add("    '   The FIT default mesh turns the 177.6 deg cell phase into")
        add("    '   122 deg -- docs/reports/2026-11-12_planar_tlm_vs_fit.md")
        add('    ChangeSolverType "HF TLM"')
        add("    With Solver")
        add('        .StimulationPort "Plane wave"')
        add('        .StimulationMode "1"')
        add('        .HardwareAcceleration "True"')
        add('        .StoreTDResultsInCache "False"')
        add("    End With")
    else:
        add("    ' ---------------- solver: FIT (diagnostic only) -----------------")
        add('    ChangeSolverType "HF Time Domain"')
        add("    With Solver")
        add('        .Method "Hexahedral"')
        add('        .StimulationPort "Plane wave"')
        add('        .StimulationMode "1"')
        add('        .SteadyStateLimit "-40"')
        add('        .MeshAdaption "False"')
        add('        .HardwareAcceleration "True"')
        add('        .StoreTDResultsInCache "False"')
        add("    End With")
    add("")
    add("    ' ---------------- optional: solve ------------------------------")
    add("    If RUN_SOLVER Then")
    add("        Solver.Start")
    add("    End If")
    add("")
    add("    ' ---------------- optional: 6-column complex far field ---------")
    add("    '   theta phi |Eth|dBsm arg(Eth) |Eph|dBsm arg(Eph)")
    add("    '   %d directions = %d x %d (theta 0..90, phi 0..%d, step %g)"
        % ((nt + 1) * nphi, nt + 1, nphi, nphi * ff_step - ff_step, ff_step))
    add("    If RUN_EXPORT Then")
    add("        Dim it, ip, i")
    add("        Dim a1, a2, a3, a4")
    add('        SelectTreeItem ("Farfields\\farfield (f=%g) [pw]")' % fmon)
    add("        FarfieldPlot.Reset")
    add("        For it = 0 To %d" % nt)
    add("            For ip = 0 To %d" % (nphi - 1))
    add('                FarfieldPlot.AddListEvaluationPoint it*%g, ip*%g, 0, "spherical", "frequency", %.0f'
        % (ff_step, ff_step, fmon * 1e9))
    add("            Next ip")
    add("        Next it")
    add('        FarfieldPlot.CalculateList ""')
    add('        a1 = FarfieldPlot.GetList("Spherical linear theta abs")')
    add('        a2 = FarfieldPlot.GetList("Spherical linear theta phase")')
    add('        a3 = FarfieldPlot.GetList("Spherical linear phi abs")')
    add('        a4 = FarfieldPlot.GetList("Spherical linear phi phase")')
    add("        Open FF_OUT For Output As #1")
    add("        For it = 0 To %d" % nt)
    add("            For ip = 0 To %d" % (nphi - 1))
    add("                i = it * %d + ip" % nphi)
    add('                Print #1, (it*%g) & " " & (ip*%g) & " " & a1(i) & " " & a2(i) & " " & a3(i) & " " & a4(i)'
        % (ff_step, ff_step))
    add("            Next ip")
    add("        Next it")
    add("        Close #1")
    add("    End If")
    add("")
    add("    ' ---------------- optional: self-check (best effort) -----------")
    add("    '   volume of a curved disc ~ pi*r^2*t:")
    add("    '   r=5.0 -> 15.708 mm3, r=4.2 -> 11.084 mm3")
    add("    If RUN_SELFCHECK Then")
    add("        On Error Resume Next")
    add("        Dim v As Double")
    add("        Dim lab As String")
    add("        Open VOL_OUT For Output As #2")
    add('        v = Solid.GetVolume("Array:substrate")')
    add('        Print #2, "substrate " & v')
    add('        v = Solid.GetVolume("Array:ground")')
    add('        Print #2, "ground " & v')
    for mi in range(n_side):
        for ni in range(n_side):
            name = "patch_%02d_%02d" % (mi, ni)
            bit = bits[mi][ni]
            add('        lab = "%s r=%.2f bit=%d"' % (name, r1 if bit else r0, bit))
            add('        v = Solid.GetVolume("Array:%s")' % name)
            add('        Print #2, lab & " vol=" & v')
    add('        Print #2, "patches = %d  (objects expected: %d)"'
        % (n_side * n_side, 2 + n_side * n_side))
    add("        Close #2")
    add("        On Error GoTo 0")
    add("    End If")
    add("")
    add("End Sub")
    return "\n".join(A) + "\n"


def verify_vba(vba: str, solver: str = SOLVER, n_side: int = N,
               ff_step: float = FF_STEP, fmon: float = FMON):
    """静态自检：返回 [(name, ok, detail), ...]。"""
    nphi = int(round(360.0 / ff_step))
    nt = int(round(90.0 / ff_step))
    checks = []
    checks.append(("Sub Main / End Sub",
                   "Sub Main()" in vba and vba.rstrip().endswith("End Sub"),
                   "wrapper present"))
    npatch = vba.count('.Name "patch_')
    checks.append(("patch definitions = %d" % (n_side * n_side),
                   npatch == n_side * n_side, "found %d" % npatch))
    nintersect = vba.count("Solid.Intersect")
    checks.append(("2 CSG intersects per patch",
                   nintersect == 2 * n_side * n_side, "found %d" % nintersect))
    if solver == "tlm":
        tag = 'ChangeSolverType "HF TLM"'
        checks.append(("ChangeSolverType HF TLM", vba.count(tag) == 1,
                       "found %d" % vba.count(tag)))
        i_solver = vba.find(tag)
        i_last = vba.rfind('.Name "patch_')
        i_solve = vba.find("Solver.Start")
        ok = i_solver > i_last and (i_solve < 0 or i_solver < i_solve)
        checks.append(("solver switch after geometry, before solve", ok,
                       "geometry@%d < solver@%d < solve@%d"
                       % (i_last, i_solver, i_solve)))
    n_nonascii = sum(1 for ch in vba if ord(ch) > 127)
    checks.append(("VBA is pure ASCII", n_nonascii == 0,
                   "non-ascii chars: %d" % n_nonascii))
    checks.append(("far-field export block", "FarfieldPlot.GetList" in vba,
                   "GetList present"))
    six = ('a1(i) & " " & a2(i) & " " & a3(i) & " " & a4(i)') in vba
    checks.append(("export writes 6 columns", six,
                   "theta phi |Eth| argEth |Eph| argEph"))
    npts = (nt + 1) * nphi
    checks.append(("%d directions" % npts, npts == 8280,
                   "%d x %d = %d" % (nt + 1, nphi, npts)))
    checks.append(("monitor name farfield (f=%g) [pw]" % fmon,
                   ("farfield (f=%g) [pw]" % fmon) in vba, "SelectTreeItem"))
    return checks


# ------------------------------------------------------------------ meta
def build_meta(n_side: int = N, radius: float = R, period: float = P,
               sub_h: float = SUB_H, er: float = ER, tan_d: float = TAN_D,
               r0: float = R0, r1: float = R1, code=CODE, block: int = BLOCK,
               bg: float = BG, patch_t: float = PATCH_T, embed: float = EMBED,
               fmin: float = FMIN, fmax: float = FMAX, fmon: float = FMON,
               ff_step: float = FF_STEP, mesh_steps: int = MESH_STEPS,
               solver: str = SOLVER, vba_path: str = "", vba_chars: int = 0):
    bits, macro, label = expand_code(code, n_side, block)
    cs = cells(n_side, period, radius)
    radii = [[(r1 if bits[m][nn] else r0) for nn in range(n_side)]
             for m in range(n_side)]
    return {
        "generated_by": "cst/r42r5_curved.py",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "vba_file": os.path.abspath(vba_path) if vba_path else "",
        "vba_chars": vba_chars,
        "method": "cylinder shell + per-cell tube/box/cutter CSG, no Bend",
        "surface": "cylinder, concave towards +z: x=R sin(u/R), z=R(1-cos(u/R))",
        "radius_mm": radius,
        "n_side": n_side,
        "block": block,
        "period_mm": period,
        "aperture_mm": n_side * period,
        "theta_max_deg": round(math.degrees(n_side * period / 2.0 / radius), 6),
        "sagitta_mm": round(radius * (1.0 - math.cos(n_side * period / 2.0 / radius)), 6),
        "substrate_thickness_mm": sub_h,
        "epsilon_r": er,
        "tan_d": tan_d,
        "patch_radius_bit0_mm": r0,
        "patch_radius_bit1_mm": r1,
        "patch_thickness_mm": patch_t,
        "patch_radius_outer_mm": round(radius + embed, 6),
        "patch_radius_inner_mm": round(radius + embed - patch_t, 6),
        "patch_lift_mm": 0.0,
        "embed_into_substrate_mm": embed,
        "ground_radius_mm": round(radius + sub_h, 6),
        "ground": "0 mm zero-thickness PEC cylindrical sheet at R+%.2f" % sub_h,
        "background_mm": bg,
        "freq_range_ghz": [fmin, fmax],
        "monitor_ghz": fmon,
        "solver": ("HF TLM (hexahedral, multigrid)" if solver == "tlm"
                   else "HF Time Domain / Hexahedral (diagnostic only)"),
        "mesh_steps_per_wavelength": int(mesh_steps),
        "ff_points": (int(round(90.0 / ff_step)) + 1) * int(round(360.0 / ff_step)),
        "ff_step_deg": ff_step,
        "ff_columns": ["theta_deg", "phi_deg", "Eth_dBsm", "argEth_deg",
                       "Eph_dBsm", "argEph_deg"],
        "code": label,
        "code_input": str(code),
        "code_macro": ["".join(str(v) for v in row) for row in macro],
        "ones": int(sum(sum(row) for row in bits)),
        "fill": round(sum(sum(row) for row in bits) / float(n_side * n_side), 4),
        "cell_radius_mm": radii,
        "patches": n_side * n_side,
        "objects_expected": 2 + n_side * n_side,
        "first_cell": {"name": "patch_00_00", "u_mm": cs[0]["u_mm"],
                       "x_mm": round(cs[0]["x_mm"], 6), "z_mm": round(cs[0]["z_mm"], 6),
                       "theta_deg": round(cs[0]["theta_deg"], 6),
                       "normal": [round(v, 6) for v in cs[0]["normal"]],
                       "radius_mm": radii[0][0]},
        "last_cell": {"name": "patch_%02d_%02d" % (n_side - 1, n_side - 1),
                      "u_mm": cs[-1]["u_mm"],
                      "x_mm": round(cs[-1]["x_mm"], 6), "z_mm": round(cs[-1]["z_mm"], 6),
                      "theta_deg": round(cs[-1]["theta_deg"], 6),
                      "normal": [round(v, 6) for v in cs[-1]["normal"]],
                      "radius_mm": radii[-1][-1]},
    }


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="生成 r42r5 曲面阵列的 CST VBA 宏（不启动 CST）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出的 .bas 路径")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成并做静态自检，不启动 CST（本脚本本来就不启动）")
    ap.add_argument("--code", default=CODE,
                    help="16 位宏码 / uniform0 / uniform1")
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--R", type=float, default=R)
    ap.add_argument("--P", type=float, default=P)
    ap.add_argument("--sub-h", type=float, default=SUB_H)
    ap.add_argument("--er", type=float, default=ER)
    ap.add_argument("--tand", type=float, default=TAN_D)
    ap.add_argument("--r0", type=float, default=R0)
    ap.add_argument("--r1", type=float, default=R1)
    ap.add_argument("--bg", type=float, default=BG)
    ap.add_argument("--patch-t", type=float, default=PATCH_T)
    ap.add_argument("--embed", type=float, default=EMBED)
    ap.add_argument("--mesh-steps", type=int, default=MESH_STEPS)
    ap.add_argument("--arc-seg", type=int, default=ARC_SEG)
    ap.add_argument("--ground-seg", type=int, default=GROUND_SEG)
    ap.add_argument("--solver", default=SOLVER, choices=("tlm", "fit"))
    ap.add_argument("--run-solver", action="store_true",
                    help="把宏里的 RUN_SOLVER 置 True（Load & Run 直接求解）")
    ap.add_argument("--run-export", action="store_true",
                    help="把宏里的 RUN_EXPORT 置 True（求解后导出 6 列远场）")
    ap.add_argument("--no-selfcheck", action="store_true",
                    help="不生成贴片体积自检块")
    ap.add_argument("--ff-out", default="", help="宏里 FF_OUT 的路径")
    args = ap.parse_args(argv)

    try:
        bits, macro, label = expand_code(args.code, args.n, BLOCK)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        print("       --code takes a 16-bit string (4x4) or uniform0 / uniform1",
              file=sys.stderr)
        return 2
    out = os.path.abspath(args.out)
    ff_out = args.ff_out or (os.path.splitext(out)[0] + "_ff.txt")
    vol_out = os.path.splitext(out)[0] + "_selfcheck.txt"

    try:
        vba = build_vba(n_side=args.n, radius=args.R, period=args.P,
                        sub_h=args.sub_h, er=args.er, tan_d=args.tand,
                        r0=args.r0, r1=args.r1, code=args.code, bg=args.bg,
                        patch_t=args.patch_t, embed=args.embed,
                        mesh_steps=args.mesh_steps, arc_seg=args.arc_seg,
                        ground_seg=args.ground_seg, solver=args.solver,
                        run_solver=args.run_solver, run_export=args.run_export,
                        run_selfcheck=not args.no_selfcheck,
                        ff_out=ff_out, vol_out=vol_out)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2

    checks = verify_vba(vba, args.solver, args.n)
    if args.solver == "fit":
        print("!! --solver fit 只用于复现 'FIT 默认网格把 177.6 deg 做成 122 deg' 的症状")

    cs = cells(args.n, args.P, args.R)
    th_max = math.degrees(args.n * args.P / 2.0 / args.R)
    print("=" * 78)
    print("r42r5 curved array   R=%.1f mm   %dx%d   block=%d   %s"
          % (args.R, args.n, args.n, BLOCK, args.solver.upper()))
    print("  aperture      %.1f mm   theta_max %.4f deg   sagitta %.4f mm"
          % (args.n * args.P, th_max,
             args.R * (1 - math.cos(args.n * args.P / 2.0 / args.R))))
    print("  patch radii   bit0 %.2f / bit1 %.2f  (shell radial %.3f .. %.3f)"
          % (args.r0, args.r1, args.R + args.embed - args.patch_t,
             args.R + args.embed))
    print("  ground        %.3f mm   background %.1f mm"
          % (args.R + args.sub_h, args.bg))
    print("  code          %s   ones=%d/%d"
          % (label, sum(sum(r) for r in bits), args.n * args.n))
    for row in macro:
        print("                " + "".join(str(v) for v in row))
    print("  first cell    patch_00_00   u=%+.1f  x=%+.4f  z=%+.4f  n=(%+.5f,0,%+.5f)"
          % (cs[0]["u_mm"], cs[0]["x_mm"], cs[0]["z_mm"],
             cs[0]["normal"][0], cs[0]["normal"][2]))
    print("  last  cell    patch_%02d_%02d   u=%+.1f  x=%+.4f  z=%+.4f  n=(%+.5f,0,%+.5f)"
          % (args.n - 1, args.n - 1, cs[-1]["u_mm"], cs[-1]["x_mm"], cs[-1]["z_mm"],
             cs[-1]["normal"][0], cs[-1]["normal"][2]))
    print("-" * 78)
    print("static checks (VBA chars=%d):" % len(vba))
    bad = 0
    for name, ok, detail in checks:
        print("  [%s] %-40s %s" % ("PASS" if ok else "FAIL", name, detail))
        bad += 0 if ok else 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    vba.encode("ascii")          # hard fail on non-ASCII（CST 按 ANSI 读）
    with open(out, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(vba)
    meta = build_meta(n_side=args.n, radius=args.R, period=args.P,
                      sub_h=args.sub_h, er=args.er, tan_d=args.tand,
                      r0=args.r0, r1=args.r1, code=args.code, bg=args.bg,
                      patch_t=args.patch_t, embed=args.embed,
                      mesh_steps=args.mesh_steps, solver=args.solver,
                      vba_path=out, vba_chars=len(vba))
    meta["static_checks"] = [{"name": n, "ok": bool(o), "detail": d}
                             for n, o, d in checks]
    meta_path = os.path.splitext(out)[0] + "_build_meta.json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print("-" * 78)
    print("wrote  %s  (%.1f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("wrote  %s" % meta_path)
    print("CST not launched (by design): load the .bas via File -> Macro -> Load VBA,")
    print("or solve the saved project and run: python cst/run_curved_case.py --project ...")
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
