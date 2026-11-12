# -*- coding: utf-8 -*-
"""Fast ESS-array builder: one cell component, Transform-copied across the grid.

No per-shape history explosion (the previous 10.8k `With Brick .Create` entries
made CST's history rebuild O(n^2) -> 17 min).  Here one state-1 cell metal is
built once in component "cell" and replicated with Transform "Shape","Matrix"
(identity matrix + translation vector), and the state-0 full sheet likewise in
component "cell0".  Lumped elements are created directly (only 2 per state-1
sub-cell).  Solver: HF Time Domain with Solver.Method "Hexahedral TLM".
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


def cell_metal_vba():
    """One state-1 cell metal, centred at (0,0), component 'cell'. Raw statements."""
    out = []
    # 4x4 coded patches mirrored 4x
    for i in range(4):
        for j in range(4):
            if CODE4[i][j] != 1:
                continue
            x0 = -(4 - j) * 1.5 - BAR_W / 2.0
            x1 = x0 + 1.5
            y1 = (4 - i) * 1.5
            y0 = y1 - 1.5
            for k, (sx, sy) in enumerate(((1, -1), (-1, -1), (1, 1), (-1, 1))):
                    ax, bx = sorted((sx * x0, sx * x1))
                    ay, by = sorted((sy * y0, sy * y1))
                    out.append("""    With Brick
        .Reset
        .Name "p_%02d_%02d_%d"
        .Component "cell"
        .Material "PEC"
        .Xrange "%g", "%g"
        .Yrange "%g", "%g"
        .Zrange "0", "0"
        .Create
    End With""" % (i, j, k, ax, bx, ay, by))
    h, r = P / 2.0, P / 2.0 - RING_W
    for k, (x0, x1, y0, y1) in enumerate([
            (-h, h, -h, -r), (-h, h, r, h), (-h, -r, -r, r), (r, h, -r, r)]):
        out.append("""    With Brick
        .Reset
        .Name "ring_%d"
        .Component "cell"
        .Material "PEC"
        .Xrange "%g", "%g"
        .Yrange "%g", "%g"
        .Zrange "0", "0"
        .Create
    End With""" % (k, x0, x1, y0, y1))
    for k, (y0, y1) in enumerate([(0, 6.0), (-6.0, 0)]):
        out.append("""    With Brick
        .Reset
        .Name "bar_%d"
        .Component "cell"
        .Material "PEC"
        .Xrange "%g", "%g"
        .Yrange "%g", "%g"
        .Zrange "0", "0"
        .Create
    End With""" % (k, -BAR_W / 2, BAR_W / 2, y0, y1))
    return "\n".join(out)


def lump_vba(cx, cy):
    out = ["Sub Main()"]
    for y1, y2 in ((7.0, 6.0), (-7.0, -6.0)):
        out.append("""    With LumpedElement
        .Reset
        .SetName "lump_%g_%g"
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
    End With""" % (cx, cy, RS, LS, cx, cy + y1, cx, cy + y2))
    out.append("End Sub")
    return "\n".join(out)


def copy_vba(src, dx, dy, dest):
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
        .Destination "%s"
        .Material ""
        .AutoDestination "True"
        .Transform "Shape", "Translate"
        .UsePickedPoints "False"
        .Vector %g, %g, 0
    End With
End Sub""" % (src, dx, dy, dest, dx, dy)


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
        ("state0 sheet", """With Brick
    .Reset
    .Name "metal0"
    .Component "cell0"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "0"
    .Create
End With""" % (-SUB * P / 2, SUB * P / 2, -SUB * P / 2, SUB * P / 2)),
        ("cell metal", cell_metal_vba()),
    ]
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=1800)
        print("  [ok] %-14s" % cap, flush=True)

    st1 = st0 = 0
    t0 = time.time()
    for mm in range(MACRO):
        for nn in range(MACRO):
            cx = (mm - (MACRO - 1) / 2.0) * SUB * P
            cy = (nn - (MACRO - 1) / 2.0) * SUB * P
            if code[mm][nn]:
                st1 += 1
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    m._execute_vba_code(copy_vba("cell", cx + dx * P / 2, cy + dy * P / 2, ""))
                    m._execute_vba_code(lump_vba(cx + dx * P / 2, cy + dy * P / 2))
            else:
                st0 += 1
                m._execute_vba_code(copy_vba("cell0", cx, cy, ""))
    print("copies done in %.0f s (state1 %d, state0 %d)" % (time.time() - t0, st1, st0), flush=True)

    # remove the template solids at the origin (they are not part of the array)
    lines = ["Sub Main()"]
    for i in m.get_tree_items():
        if i.startswith("Components\\cell\\") or i.startswith("Components\\cell0\\"):
            lines.append('    Solid.Delete "%s"' % i.split("Components\\")[1].replace("\\", ":"))
    lines.append("End Sub")
    m._execute_vba_code("\n".join(lines))
    print("template solids removed", flush=True)

    # local mesh refinement 0.2 mm on every coding-cell metal solid (the copies
    # live in components cell_1 ... cell_N).  One VBA block -> fast.
    ref = ["Sub Main()"]
    for i in m.get_tree_items():
        if i.startswith("Components\\cell_") and i.count("\\") == 2:
            nm = i.split("Components\\")[1].replace("\\", ":")
            ref.append('    Solid.SetAutomeshStepWidth "%s", 0.2, 0.2, 0.0' % nm)
    ref.append("End Sub")
    t0 = time.time()
    m._execute_vba_code("\n".join(ref))
    print("local 0.2 mm refinement on %d coding-cell solids in %.0f s"
          % (len(ref) - 2, time.time() - t0), flush=True)

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

    names = [i.split("\\")[-1] for i in m.get_tree_items() if i.startswith("Components\\")]
    cell = [i for i in m.get_tree_items() if i.startswith("Components\\cell\\")]
    cell0 = [i for i in m.get_tree_items() if i.startswith("Components\\cell0\\")]
    print("components: %s | cell solids %d | cell0 solids %d" % (names, len(cell), len(cell0)), flush=True)

    prj.save(OUT, include_results=False, allow_overwrite=True)
    print("saved:", OUT, flush=True)


if __name__ == "__main__":
    main()
