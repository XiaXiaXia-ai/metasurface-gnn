# -*- coding: utf-8 -*-
"""Mesh-convergence check of the two unit cells' reflection phase.

Same periodic cell as the array (14 mm, material1 er 2.65 / tanD 0.0013,
h 1.5 mm, PEC ground, circular PEC patch), Floquet ports at both z ends,
normal incidence TE(0,0)/TM(0,0), frequency domain + tetrahedral mesh.

The mesh is refined through Mesh.StepsPerWavelengthTet (maximum edge length as
a fraction of a wavelength) and |S11| / phase at 10 GHz are compared, so the
180 deg design condition can be checked for mesh convergence.
"""
import os
import sys

import numpy as np

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface
import cst.results

P = 14.0
SUB_H = 1.5
FMIN, FMAX, F0 = 9.0, 11.0, 10.0
HALF = P / 2.0
EPS, TAND = 2.65, 0.0013
OUT = r"D:\cell_mesh"
RADII = (4.7, 2.0)
STEPS = (None, 6, 8, 12)          # None -> CST default


def model_vba(r, steps):
    mesh_extra = "" if steps is None else \
        "    With Mesh\n        .StepsPerWavelengthTet %g\n    End With\n" % steps
    return """
Sub Main()
    With Units
        .SetUnit "Length", "mm"
        .SetUnit "Frequency", "GHz"
        .SetUnit "Time", "ns"
    End With
    Solver.FrequencyRange "%(fmin)g", "%(fmax)g"
    With Background
        .Type "Normal"
        .Epsilon "1.0"
        .Mu "1.0"
        .XminSpace "0.0"
        .XmaxSpace "0.0"
        .YminSpace "0.0"
        .YmaxSpace "0.0"
        .ZminSpace "0.0"
        .ZmaxSpace "0.0"
    End With
    With FloquetPort
        .Reset
        .SetDialogTheta "0"
        .SetDialogPhi "0"
        .SetSortCode "+beta/pw"
        .SetCustomizedListFlag "False"
        .Port "Zmin"
        .SetNumberOfModesConsidered "2"
        .Port "Zmax"
        .SetNumberOfModesConsidered "2"
    End With
    MakeSureParameterExists "theta", "0"
    MakeSureParameterExists "phi", "0"
    With Boundary
        .Xmin "unit cell"
        .Xmax "unit cell"
        .Ymin "unit cell"
        .Ymax "unit cell"
        .Zmin "expanded open"
        .Zmax "expanded open"
        .Xsymmetry "none"
        .Ysymmetry "none"
        .Zsymmetry "none"
        .XPeriodicShift "0.0"
        .YPeriodicShift "0.0"
        .ZPeriodicShift "0.0"
        .PeriodicUseConstantAngles "False"
        .SetPeriodicBoundaryAngles "theta", "phi"
        .SetPeriodicBoundaryAnglesDirection "inward"
        .UnitCellFitToBoundingBox "True"
        .UnitCellDs1 "0.0"
        .UnitCellDs2 "0.0"
        .UnitCellAngle "90.0"
    End With
    With Material
        .Reset
        .Name "material1"
        .FrqType "all"
        .Type "Normal"
        .MaterialUnit "Frequency", "GHz"
        .MaterialUnit "Geometry", "mm"
        .Epsilon "%(eps)g"
        .Mu "1"
        .Sigma "0.0"
        .TanD "%(tand)g"
        .TanDFreq "0.0"
        .TanDGiven "True"
        .TanDModel "ConstTanD"
        .Colour "0", "1", "1"
        .Create
    End With
    With Brick
        .Reset
        .Name "solid1"
        .Component "component1"
        .Material "material1"
        .Xrange "%(nh)g", "%(h)g"
        .Yrange "%(nh)g", "%(h)g"
        .Zrange "0", "%(sh)g"
        .Create
    End With
    With Cylinder
        .Reset
        .Name "solid2"
        .Component "component1"
        .Material "PEC"
        .OuterRadius "%(r)g"
        .InnerRadius "0"
        .Axis "z"
        .Zrange "%(sh)g", "%(sh)g"
        .Xcenter "0"
        .Ycenter "0"
        .Segments "0"
        .Create
    End With
    With Brick
        .Reset
        .Name "solid3"
        .Component "component1"
        .Material "PEC"
        .Xrange "%(nh)g", "%(h)g"
        .Yrange "%(nh)g", "%(h)g"
        .Zrange "0", "0"
        .Create
    End With
    With Mesh
        .MeshType "Tetrahedral"
    End With
%(mesh)s    With FDSolver
        .Reset
        .Stimulation "List", "List"
        .ResetExcitationList
        .AddToExcitationList "Zmax", "TE(0,0);TM(0,0)"
        .LowFrequencyStabilization "False"
    End With
    With MeshSettings
        .SetMeshType "Tet"
        .Set "Version", 1
    End With
    ChangeSolverType "HF Frequency Domain"
End Sub
""" % dict(fmin=FMIN, fmax=FMAX, h=HALF, nh=-HALF, sh=SUB_H, r=r,
           eps=EPS, tand=TAND, mesh=mesh_extra)


def read_10g(path):
    prj = cst.results.ProjectFile(path, allow_interactive=True)
    item = prj.get_3d().get_result_item(r"1D Results\S-Parameters\SZmax(1),Zmax(1)")
    rows = item.get_data()
    x = np.array([row[0] for row in rows], float)
    y = np.array([complex(row[1]) for row in rows])
    k = int(np.argmin(np.abs(x - F0)))
    return x[k], y[k]


def main():
    os.makedirs(OUT, exist_ok=True)
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    try:
        de.set_quiet_mode(True)
    except Exception:
        pass

    res = {}
    for r in RADII:
        for st in STEPS:
            tag = "default" if st is None else "s%g" % st
            path = os.path.join(OUT, "cell_r%g_%s.cst" % (r, tag))
            if os.path.isfile(path):
                try:
                    _, s = read_10g(path)
                    res[(r, st)] = s
                    print("[reuse] r=%.2f %-7s |S11|=%6.2f dB  phase=%7.1f"
                          % (r, tag, 20*np.log10(abs(s)), np.degrees(np.angle(s))), flush=True)
                    continue
                except Exception:
                    pass
            prj = de.new_mws()
            m = prj.model3d
            m._execute_vba_code(model_vba(r, st))
            prj.save(path, include_results=False, allow_overwrite=True)
            m.run_solver()
            prj.save(include_results=True, allow_overwrite=True)
            prj.close()
            _, s = read_10g(path)
            res[(r, st)] = s
            print("[solve] r=%.2f %-7s |S11|=%6.2f dB  phase=%7.1f"
                  % (r, tag, 20*np.log10(abs(s)), np.degrees(np.angle(s))), flush=True)

    print("\n%-10s %10s %10s %10s %10s" % ("mesh", "r4.7 phase", "r2.0 phase", "delta", "|d| vs 180"))
    for st in STEPS:
        tag = "default" if st is None else "s%g" % st
        a = np.degrees(np.angle(res[(4.7, st)]))
        b = np.degrees(np.angle(res[(2.0, st)]))
        d = (a - b + 180) % 360 - 180
        print("%-10s %10.2f %10.2f %10.2f %10.2f" % (tag, a, b, d, abs(abs(d) - 180)))


if __name__ == "__main__":
    main()
