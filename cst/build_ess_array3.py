# -*- coding: utf-8 -*-
"""Fast ESS-array builder v3: one 2x2 macro MODULE per state, transform-copied.

Module "mod1" = one 30x30 mm macro cell with 4 ESS sub-cells (metal + 8 lumped
elements), built once at the origin and copied to every state-1 macro position.
Module "mod0" = the full-metal 30x30 sheet, copied to every state-0 position.
Solver: HF Time Domain, Solver.Method "Hexahedral TLM".  A 0.2 mm local mesh
refinement (Absolute) is applied to all coding-cell metal after the copies.
"""
import random
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

P = 15.0
SUB = 2
H = 3.0
RING_W, BAR_W = 0.5, 1.0
RS, LS = 3.0, 0.45e-9
FMIN, FMAX, FMON = 8.0, 12.0, 10.0
BG = 15.0
CODE4 = [[1, 1, 1, 1],
         [0, 1, 0, 1],
         [0, 1, 0, 1],
         [1, 1, 1, 0]]
MACRO = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SEED = 20261111
L = P * SUB * MACRO
HALF = L / 2.0
OUT = r"D:\META_ess_array10.cst"

rng = random.Random(SEED)
code = [[rng.randint(0, 1) for _ in range(MACRO)] for _ in range(MACRO)]


def brick(out, nm, comp, x0, x1, y0, y1, z0="0", z1="0", mat="PEC"):
    out.append("""    With Brick
        .Reset
        .Name "%s"
        .Component "%s"
        .Material "%s"
        .Xrange "%g", "%g"
        .Yrange "%g", "%g"
        .Zrange "%s", "%s"
        .Create
    End With""" % (nm, comp, mat, x0, x1, y0, y1, z0, z1))


def module1_vba():
    """One state-1 macro module (2x2 ESS sub-cells) centred at (0,0)."""
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
                    brick(out, "p_%d_%02d_%02d_%d" % (s, i, j, k), "mod1", ax, bx, ay, by)
        h, r = P / 2.0, P / 2.0 - RING_W
        for k, (x0, x1, y0, y1) in enumerate([
                (sx - h, sx + h, sy - h, sy - r), (sx - h, sx + h, sy + r, sy + h),
                (sx - h, sx - r, sy - r, sy + r), (sx + r, sx + h, sy - r, sy + r)]):
            brick(out, "ring_%d_%d" % (s, k), "mod1", x0, x1, y0, y1)
        for k, (y0, y1) in enumerate(((sy, sy + 6.0), (sy - 6.0, sy))):
            brick(out, "bar_%d_%d" % (s, k), "mod1", sx - BAR_W / 2, sx + BAR_W / 2, y0, y1)
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


def binary_merge(m, groups):
    lines = ["Sub Main()"]
    for g in groups:
        if len(g) <= 1:
            continue
        cur = g
        while len(cur) > 1:
            nxt = []
            i = 0
            while i < len(cur):
                if i + 1 < len(cur):
                    lines.append('    Solid.Add "%s", "%s"' % (cur[i], cur[i + 1]))
                    nxt.append(cur[i])
                    i += 2
                else:
                    nxt.append(cur[i])
                    i += 1
            cur = nxt
    lines.append("End Sub")
    if len(lines) > 2:
        m._execute_vba_code("\n".join(lines))


def merge_module_metal(m):
    """Merge ALL of mod1's top metal into one solid before copying.

    Every piece is coplanar at z = 0, so Solid.Add merges them into a single
    (multi-shell) sheet solid; disconnected pieces are allowed for coplanar
    sheets, and On Error Resume Next keeps the script alive if one fails.
    """
    names = ["mod1:" + i.split("\\")[-1] for i in m.get_tree_items()
             if i.startswith("Components\\mod1\\")]
    if len(names) <= 1:
        return
    base = names[0]
    lines = ["Sub Main()"]
    for nm in names[1:]:
        lines.append("    On Error Resume Next")
        lines.append('    Solid.Add "%s", "%s"' % (base, nm))
    lines.append("End Sub")
    m._execute_vba_code("\n".join(lines))


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


def main():
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)
    for p in de.get_open_projects():
        try:
            if p.filename().lower().endswith("meta_ess_array10.cst"):
                try:
                    p.close()
                except Exception:
                    pass
        except Exception:
            pass

    prj = de.new_mws()
    time.sleep(1.0)
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
        ("substrate", """With Brick
    .Reset
    .Name "substrate"
    .Component "Array"
    .Material "Vacuum"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "%g", "0"
    .Create
End With""" % (-HALF, HALF, -HALF, HALF, -H)),
        ("ground", """With Brick
    .Reset
    .Name "ground"
    .Component "Array"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "%g", "%g"
    .Create
End With""" % (-HALF, HALF, -HALF, HALF, -H, -H)),
        ("module0 sheet", """With Brick
    .Reset
    .Name "metal0"
    .Component "mod0"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "0"
    .Create
End With""" % (-SUB * P / 2, SUB * P / 2, -SUB * P / 2, SUB * P / 2)),
        ("module1 (2x2 ESS cells)", module1_vba()),
    ]
    t0 = time.time()
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=1800)
        print("  [ok] %-24s %.0fs" % (cap, time.time() - t0), flush=True)

    # boolean-merge the module's top metal before copying
    t0 = time.time()
    merge_module_metal(m)
    left = [i.split("\\")[-1] for i in m.get_tree_items() if i.startswith("Components\\mod1\\")]
    print("module metal merged in %.0f s -> %d solids" % (time.time() - t0, len(left)), flush=True)

    st1 = st0 = 0
    t0 = time.time()
    lump_lines = ["Sub Main()"]
    for mm in range(MACRO):
        for nn in range(MACRO):
            cx = (mm - (MACRO - 1) / 2.0) * SUB * P
            cy = (nn - (MACRO - 1) / 2.0) * SUB * P
            if code[mm][nn]:
                st1 += 1
                m._execute_vba_code(copy_vba("mod1", cx, cy))
                for s, (dx, dy) in enumerate(((-7.5, -7.5), (7.5, -7.5), (-7.5, 7.5), (7.5, 7.5))):
                    lump_lines.append(lump_vba(cx + dx, cy + dy, s))
            else:
                st0 += 1
                m._execute_vba_code(copy_vba("mod0", cx, cy))
    lump_lines.append("End Sub")
    m._execute_vba_code("\n".join(lump_lines))
    print("copies + lumps done in %.0f s (state1 %d, state0 %d)" % (time.time() - t0, st1, st0), flush=True)

    # delete the origin templates
    lines = ["Sub Main()"]
    for i in m.get_tree_items():
        if i.startswith("Components\\mod1\\") or i.startswith("Components\\mod0\\"):
            lines.append('    Solid.Delete "%s"' % i.split("Components\\")[1].replace("\\", ":"))
    lines.append("End Sub")
    m._execute_vba_code("\n".join(lines))
    print("templates removed", flush=True)

    # ---- GLOBAL mesh settings (Hexahedral TLM), CST's own HexTLM keys ----
    #   max cell : 15 cells per wavelength, 20 cells per max model-box edge (near)
    #   min cell : ABSOLUTE 0.2 mm  (UseRatioLimitGeometry 0 + MinStepGeometry*)
    m.add_to_history("mesh settings", """With Mesh
    .MeshType "HexahedralTLM"
    .SetCreator "High Frequency"
End With
With MeshSettings
    .SetMeshType "HexTLM"
    .Set "Version", 1%
    .Set "StepsPerWaveNear", "15"
    .Set "StepsPerWaveFar", "15"
    .Set "WavelengthRefinementSameAsNear", "1"
    .Set "StepsPerBoxNear", "20"
    .Set "StepsPerBoxFar", "1"
    .Set "ModelBoxDescrNear", "maxedge"
    .Set "ModelBoxDescrFar", "maxedge"
    .Set "UseRatioLimitGeometry", "0"
    .Set "UseSameMinStepGeometryXYZ", "1"
    .Set "MinStepGeometryX", "0.2"
    .Set "MinStepGeometryY", "0.2"
    .Set "MinStepGeometryZ", "0.2"
End With""", timeout=600)
    print("  [ok] global mesh: HexTLM, 15/λ, 20/box-edge, min cell 0.2 mm absolute", flush=True)

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

    prj.save(OUT, include_results=False, allow_overwrite=True)
    print("saved:", OUT, flush=True)

    t0 = time.time()
    try:
        m.add_to_history("mesh", "Mesh.Update", timeout=3600)
        print("TLM mesh %.0f s | cells %d | Nx=%d Ny=%d Nz=%d | min step %.4f | hex type %s"
              % (time.time() - t0, m.Mesh.GetNumberOfMeshCells(),
                 m.Mesh.GetNx(), m.Mesh.GetNy(), m.Mesh.GetNz(),
                 m.Mesh.GetActualSmallestHexMeshStep(), m.Mesh.GetActiveHexMeshType()), flush=True)
    except Exception as e:
        print("mesh failed after %.0f s: %s" % (time.time() - t0, str(e).replace("\n", " ")[:160]), flush=True)


if __name__ == "__main__":
    main()
