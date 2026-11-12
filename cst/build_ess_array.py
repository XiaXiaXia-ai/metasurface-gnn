# -*- coding: utf-8 -*-
"""Build the ESS-cell coding array: 10x10 macro cells, each 2x2 sub-cells.

State 1 = the Reflect_ESS unit cell (diode ON, R = 3 Ohm / L = 0.45 nH):
          4x4 coded PEC patches mirrored 4x, PEC ring, two bars, two lumped
          elements -- period 15 mm, vacuum substrate 3 mm, PEC ground at z=-3.
State 0 = the same substrate and ground, but the whole 30x30 macro cell is
          covered by a solid PEC sheet at z = 0.

Usage:  python build_ess_array.py [MACRO]      (default 10)
The project is built and saved, the solver is NOT run.
"""
import os
import random
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

P = 15.0                    # sub-cell period (mm)
SUB = 2                     # sub-cells per macro cell (each direction)
H = 3.0                     # substrate thickness (mm)
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
OUT = r"D:\META_ess_array%d.cst" % MACRO

rng = random.Random(SEED)
code = [[rng.randint(0, 1) for _ in range(MACRO)] for _ in range(MACRO)]

_n = [0]


def name(prefix):
    _n[0] += 1
    return "%s_%05d" % (prefix, _n[0])


def brick(x0, x1, y0, y1, z0, z1, comp="Array", mat="PEC", tag="s"):
    return ("""With Brick
    .Reset
    .Name "%s"
    .Component "%s"
    .Material "%s"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "%g", "%g"
    .Create
End With
""" % (name(tag), comp, mat, x0, x1, y0, y1, z0, z1))


def lump(cx, cy, y1, y2):
    return ("""With LumpedElement
    .Reset
    .SetName "%s"
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
End With
""" % (name("lump"), RS, LS, cx, cy + y1, cx, cy + y2))


def state1_cell(cx, cy):
    """One ESS sub-cell centred at (cx, cy)."""
    out = []
    # 4x4 coded patches, mirrored in x, in y and in both
    for i in range(4):
        for j in range(4):
            if CODE4[i][j] != 1:
                continue
            x0 = -(4 - j) * 1.5 - BAR_W / 2.0
            x1 = x0 + 1.5
            y1 = (4 - i) * 1.5
            y0 = y1 - 1.5
            for sx in (1, -1):
                for sy in (1, -1):
                    ax, bx = sorted((cx + sx * x0, cx + sx * x1))
                    ay, by = sorted((cy + sy * y0, cy + sy * y1))
                    out.append(brick(ax, bx, ay, by, 0, 0, tag="p"))
    # PEC ring (4 strips, width RING_W, outer edge at +-P/2)
    h, r = P / 2.0, P / 2.0 - RING_W
    out.append(brick(cx - h, cx + h, cy - h, cy - r, 0, 0, tag="ring"))
    out.append(brick(cx - h, cx + h, cy + r, cy + h, 0, 0, tag="ring"))
    out.append(brick(cx - h, cx - r, cy - r, cy + r, 0, 0, tag="ring"))
    out.append(brick(cx + r, cx + h, cy - r, cy + r, 0, 0, tag="ring"))
    # two bars feeding the lumped elements
    out.append(brick(cx - BAR_W / 2, cx + BAR_W / 2, cy, cy + 6.0, 0, 0, tag="bar"))
    out.append(brick(cx - BAR_W / 2, cx + BAR_W / 2, cy - 6.0, cy, 0, 0, tag="bar"))
    # diode ON: R + L between bar end and ring inner edge
    out.append(lump(cx, cy, 7.0, 6.0))
    out.append(lump(cx, cy, -7.0, -6.0))
    return out


def state0_cell(cx, cy):
    """Solid PEC top over the whole macro cell (2x2 sub-cells)."""
    half = SUB * P / 2.0
    return [brick(cx - half, cx + half, cy - half, cy + half, 0, 0, tag="metal")]


def build_blocks():
    blocks = []
    blocks.append(("units", """With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
    .SetUnit "Time", "ns"
End With
"""))
    blocks.append(("frequency range", 'Solver.FrequencyRange "%g", "%g"' % (FMIN, FMAX)))
    blocks.append(("background", """With Background
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
""" % ((BG,) * 6)))
    blocks.append(("boundary", """With Boundary
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
""" % ((FMIN + FMAX) / 2.0,)))
    blocks.append(("substrate", brick(-HALF, HALF, -HALF, HALF, -H, 0,
                                      mat="Vacuum", tag="substrate")))
    blocks.append(("ground", brick(-HALF, HALF, -HALF, HALF, -H, -H, tag="gnd")))

    st1 = st0 = 0
    for m in range(MACRO):
        for n in range(MACRO):
            cx = (m - (MACRO - 1) / 2.0) * SUB * P
            cy = (n - (MACRO - 1) / 2.0) * SUB * P
            parts = []
            if code[m][n]:
                st1 += 1
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        parts += state1_cell(cx + dx * P / 2.0, cy + dy * P / 2.0)
            else:
                st0 += 1
                parts += state0_cell(cx, cy)
            blocks.append(("macro %02d_%02d" % (m, n), "".join(parts)))

    blocks.append(("plane wave", """With PlaneWave
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
""" % FMON))
    blocks.append(("farfield monitor", """With Monitor
    .Reset
    .Name "farfield (f=%g)"
    .Domain "Frequency"
    .FieldType "Farfield"
    .MonitorValue "%g"
    .UseSubvolume "False"
    .ExportFarfieldSource "False"
    .Create
End With
""" % (FMON, FMON)))
    blocks.append(("solver", """With Solver
    .Method "Tetrahedral"
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
"""))
    return blocks, st1, st0


def main():
    blocks, st1, st0 = build_blocks()
    print("macro %dx%d | sub-cells %d | state1 %d, state0 %d | array %.0f mm"
          % (MACRO, MACRO, MACRO * MACRO * SUB * SUB, st1, st0, L), flush=True)
    print("blocks: %d | VBA size %.1f MB" % (len(blocks),
          sum(len(b) for _, b in blocks) / 1e6), flush=True)

    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)
    prj = de.new_mws()
    time.sleep(1.0)
    m = prj.model3d
    t0 = time.time()
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=1800)
        print("  [ok] %-14s %.1fs" % (cap, time.time() - t0), flush=True)
    objs = [i for i in m.get_tree_items() if i.startswith("Components\\Array\\")]
    print("built in %.0f s | Array objects: %d" % (time.time() - t0, len(objs)), flush=True)

    prj.save(OUT, include_results=False, allow_overwrite=True)
    print("saved:", OUT, flush=True)
    print("next: Mesh.Update to see the cell count, then run", flush=True)


if __name__ == "__main__":
    main()
