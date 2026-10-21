# -*- coding: utf-8 -*-
"""Characterise the unit cell with the NEW substrate (er 2.65, tanD 0.0013).

Same setup as the original cell characterisation (build_unit_ref.py): 14 mm
period, 1.5 mm substrate, PEC ground, circular PEC patch, Floquet ports at both
z ends, unit cell in x/y, tetrahedral mesh + frequency domain solver, normal
incidence TE(0,0)/TM(0,0).

The point is to find where the 180 deg phase difference lands with the new
dielectric: er dropped from 4.3 to 2.65, so the resonance moves to a larger
radius and the old pair (3.65 / 5.60 mm) no longer codes.
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface
import cst.results

P = 14.0
SUB_H = 1.5
FMIN, FMAX, F0 = 9.0, 11.0, 10.0
HALF = P / 2.0
EPS = 2.65
TAND = 0.0013
RADII = [4.0, 4.5, 5.0, 5.6, 6.5, 7.0]


def model_vba(r):
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
    With FDSolver
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
           eps=EPS, tand=TAND)


def read_10g(path):
    prj = cst.results.ProjectFile(path, allow_interactive=True)
    r3 = prj.get_3d()
    item = r3.get_result_item(r"1D Results\S-Parameters\SZmax(1),Zmax(1)")
    rows = item.get_data()
    x = np.array([row[0] for row in rows], float)
    y = np.array([complex(row[1]) for row in rows])
    k = int(np.argmin(np.abs(x - F0)))
    return x[k], y[k]


def main():
    de = cst.interface.DesignEnvironment.connect_to_any()
    res = {}
    for r in RADII:
        path = r"D:\cell_er265_r%g.cst" % r
        if os.path.isfile(path):
            try:
                _, s = read_10g(path)
                res[r] = s
                print("[reuse] r=%.2f  |S11|=%6.2f dB  phase=%7.1f"
                      % (r, 20 * np.log10(abs(s)), np.degrees(np.angle(s))), flush=True)
                continue
            except Exception:
                pass
        t0 = time.time()
        prj = de.new_mws()
        m3d = prj.model3d
        m3d._execute_vba_code(model_vba(r))
        prj.save(path, include_results=False, allow_overwrite=True)
        m3d.run_solver()
        prj.save(include_results=True, allow_overwrite=True)
        prj.close()
        _, s = read_10g(path)
        res[r] = s
        print("[solve] r=%.2f  |S11|=%6.2f dB  phase=%7.1f  (%.0f s)"
              % (r, 20 * np.log10(abs(s)), np.degrees(np.angle(s)),
                 time.time() - t0), flush=True)

    print("\n r(mm)   |S11| dB   phase deg")
    for r in sorted(res):
        s = res[r]
        print("%5.2f   %7.2f   %8.1f" % (r, 20 * np.log10(abs(s)),
                                         np.degrees(np.angle(s))))
    print("\nphase step per 0.1 mm:")
    rs = sorted(res)
    for a, b in zip(rs, rs[1:]):
        d = (np.degrees(np.angle(res[b])) - np.degrees(np.angle(res[a])) + 180) % 360 - 180
        print("  %.2f -> %.2f : %6.1f deg / %.2f mm" % (a, b, d, b - a))


if __name__ == "__main__":
    main()
