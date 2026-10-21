# -*- coding: utf-8 -*-
"""Build a 20x20 1-bit reflection coding metasurface in CST (no solver run).

Unit cell (new substrate, characterised 2026-10-21):
    period 14 mm, "material1" (er = 2.65, tanD = 0.0013) h = 1.5 mm, PEC ground
    at z = 0, circular PEC patch at z = 1.5 mm:
        r = 4.7 mm -> phase  -5.3 deg, |S11| = -1.24 dB   (bit 0, 0 deg)
        r = 2.0 mm -> phase 174.6 deg, |S11| = -1.39 dB   (bit 1, 180 deg)
    phase difference 179.95 deg, amplitude imbalance 0.15 dB.

Domain / boundary  (rev 2 -- read before changing anything)
-----------------------------------------------------------
* Six "expanded open" faces.  The surrounding space is NOT built from vacuum
  padding bricks (rev 1 did that in a different script and it did not match
  the PEC reference model); it is set here, in the Background properties, via
  BG_SPACE on all six sides -- exactly what the "Background Properties" dialog
  shows.
* Minimum distance = lambda/4 at the centre of the band, and the frequency
  written next to it is the band centre as well.  Rev 1 wrote FMIN while the
  reference type was "Center", which made that number a silent no-op
  (CST then uses the centre, 10 GHz -> 7.49 mm, not 9 GHz -> 8.33 mm).
* build_pec_plate.py must use the SAME BG_SPACE.  Otherwise the array and its
  PEC reference sit in different calculation domains and the "specular
  suppression" numbers are not comparable.
* Monitors: 9.8 / 9.9 / 10.0 / 10.1 / 10.2 GHz (a 0.1 GHz grid around the
  design frequency).  Extra monitor frequencies do NOT need another solve --
  each one only adds a surface integration on the calculation box -- but they
  must be declared BEFORE the run: StoreTDResultsInCache is off, so a monitor
  missing from this list cannot be reconstructed afterwards.
"""
import os
import random
import sys
import time

CST_LIB = r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries"
if os.path.isdir(CST_LIB) and CST_LIB not in sys.path:
    sys.path.insert(0, CST_LIB)

import cst.interface  # noqa: E402

# ---------------- parameters ----------------
P = 14.0            # unit cell period (mm)
N = 20              # 20 x 20
BLOCK = 2           # one code bit covers a BLOCK x BLOCK macro cell (N stays 20)
R0 = 4.7            # bit 0 -> -5.3 deg  (er 2.65 substrate)
R1 = 2.0            # bit 1 -> 174.6 deg
SUB_H = 1.5         # substrate thickness (mm)
FMIN, FMAX = 9.0, 11.0
FMON = 10.0
SEED = 20261020
OUT = r"D:\META_coding_array_er265_r2_b2.cst"

C0 = 299.792458     # speed of light in mm*GHz
LAM0 = C0 / FMON    # 29.98 mm at 10 GHz

BG_SPACE = 15.0     # Background surrounding space, all 6 sides (LAM0/2).  DEFAULT.
# Validated 2026-10-21 with a 3-case sweep (D:\bg_sweep, bg_distance_sweep.py):
#   - a request below lambda/4 is clamped up to 7.49 mm by the expanded-open
#     minimum distance, so 5 mm and 7.5 mm are the same run;
#   - 7.5 / 15 / 30 mm differ by only 0.19 dB in the specular level, but the
#     deep nulls are not converged at 7.5 mm (up to 9 dB scatter there);
#   - 15 and 30 mm agree to 0.01 dB, so 30 mm only costs 89 s and +83% cells.
# 15 mm is therefore the smallest domain with a converged pattern.  Do not
# raise it without a new sweep, and do not lower it below lambda/4.
MESH_STEPS = 20     # hex lines per wavelength; 0 -> keep the CST default
STEADY_STATE = "-40"
FARFIELD_FREQS = (9.8, 9.9, FMON, 10.1, 10.2)   # 0.1 GHz grid around the design frequency

L = N * P           # 280 mm
half = L / 2.0

# code bits live on BLOCK x BLOCK macro cells; the element count is unchanged
NB = N // BLOCK
rng = random.Random(SEED)
bits = [[rng.randint(0, 1) for _ in range(NB)] for _ in range(NB)]
code = [[bits[m // BLOCK][n // BLOCK] for n in range(N)] for m in range(N)]

# ---------------- VBA blocks ----------------
vba = []

vba.append(("define units", """'set the units
With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
    .SetUnit "Voltage", "V"
    .SetUnit "Resistance", "Ohm"
    .SetUnit "Inductance", "nH"
    .SetUnit "Temperature", "degC"
    .SetUnit "Time", "ns"
    .SetUnit "Current", "A"
    .SetUnit "Conductance", "S"
    .SetUnit "Capacitance", "pF"
End With
"""))

vba.append(("define frequency range",
            'Solver.FrequencyRange "%g", "%g"' % (FMIN, FMAX)))

vba.append(("define boundary", """With Boundary
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

# surrounding space lives here (Background properties), not in extra bricks
vba.append(("define background", """With Background
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
""" % ((BG_SPACE,) * 6)))

vba.append(("define material", """With Material
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
"""))

# substrate (one brick for the whole array)
vba.append(("build substrate", """With Brick
    .Reset
    .Name "substrate"
    .Component "Array"
    .Material "material1"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "%g"
    .Create
End With
""" % (-half, half, -half, half, SUB_H)))

# PEC ground plane
vba.append(("build ground", """With Brick
    .Reset
    .Name "ground"
    .Component "Array"
    .Material "PEC"
    .Xrange "%g", "%g"
    .Yrange "%g", "%g"
    .Zrange "0", "0"
    .Create
End With
""" % (-half, half, -half, half)))

# 400 circular patches
patches = []
for m in range(N):
    for n in range(N):
        x = (m - (N - 1) / 2.0) * P
        y = (n - (N - 1) / 2.0) * P
        r = R1 if code[m][n] else R0
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

vba.append(("build 400 patches", "".join(patches)))

# plane wave: normal incidence (-z), x polarization
vba.append(("define plane wave", """With PlaneWave
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

# farfield monitors: one per frequency, CST adds the " [pw]" suffix to the name
for f in FARFIELD_FREQS:
    mon = "farfield (f=%g)" % f
    vba.append(("define farfield monitor: " + mon, """With Monitor
    .Reset
    .Name "%s"
    .Domain "Frequency"
    .FieldType "Farfield"
    .MonitorValue "%g"
    .UseSubvolume "False"
    .ExportFarfieldSource "False"
    .Create
End With
""" % (mon, f)))

# time domain solver (hexahedral, plane wave, GPU)
# NOTE: ChangeSolverType must come BEFORE "With Solver", otherwise switching
#       the solver module resets everything configured above it.
vba.append(("solver type", 'ChangeSolverType "HF Time Domain"'))

vba.append(("configure T solver", """With Solver
    .Method "Hexahedral"
    .StimulationPort "Plane wave"
    .StimulationMode "1"
    .SteadyStateLimit "%s"
    .MeshAdaption "False"
    .HardwareAcceleration "True"
    .StoreTDResultsInCache "False"
    .RunDiscretizerOnly "False"
    .FullDeembedding "False"
    .SuperimposePLWExcitation "False"
    .UseSensitivityAnalysis "False"
End With
""" % STEADY_STATE))

# mesh: the default mesh only gives 1-2 cells through the 1.5 mm substrate at
# 10-11 GHz, so raise the global density.  Note the two different objects:
# "Version" is a MeshSettings key, while LinesPerWavelength is a Mesh method
# (CST 2026: MeshSettings has no "StepsPerWave" keyword).
# Set MESH_STEPS = 0 to keep the CST default (then still run the convergence
# check on one code before trusting the pattern).
mesh_code = """With MeshSettings
    .SetMeshType "Hex"
    .Set "Version", 1
End With
"""
if MESH_STEPS:
    mesh_code += """With Mesh
    .LinesPerWavelength %d
End With
""" % MESH_STEPS
vba.append(("set hex mesh", mesh_code))

vba.append(("zoom", "Plot.ZoomToStructure"))

# VBA property names that differ between CST versions: if one of these fails,
# report it and keep building instead of aborting on a cosmetic detail.
OPTIONAL_CAPTIONS = {"set hex mesh"}


def main():
    print("connecting to CST ...")
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    prj = de.new_mws()
    time.sleep(1.0)

    m3d = prj.model3d
    try:
        for caption, code_txt in vba:
            t0 = time.time()
            try:
                m3d.add_to_history(caption, code_txt, timeout=600)
            except Exception as exc:  # noqa: BLE001
                if caption in OPTIONAL_CAPTIONS:
                    print("  [skip] %-45s %s" % (caption, exc))
                    continue
                raise
            print("  [ok] %-45s %.1fs" % (caption, time.time() - t0))
    except Exception:
        # deliberately not closed: the half-built project stays open so the
        # failing block can be inspected in the history list.  Nothing is saved.
        print("build failed -> project left OPEN and NOT saved (check the history)")
        raise

    prj.save(OUT, include_results=False, allow_overwrite=True)
    print("saved:", OUT)

    print("\nbackground box: %.1f x %.1f x %.1f mm (BG_SPACE = %.1f mm on all sides)"
          % (L + 2 * BG_SPACE, L + 2 * BG_SPACE, SUB_H + 2 * BG_SPACE, BG_SPACE))
    print("lambda  : %.2f mm @ %.1f GHz | P = %.3f lambda | array = %.2f lambda"
          % (LAM0, FMON, P / LAM0, L / LAM0))
    print("minimum distance: lambda/4 @ %.1f GHz = %.2f mm"
          % ((FMIN + FMAX) / 2.0, LAM0 / 4.0))
    print("monitors: " + ", ".join("farfield (f=%g) [pw]" % f for f in FARFIELD_FREQS))

    ones = sum(sum(row) for row in code)
    print("coding: %d ones / %d zeros" % (ones, N * N - ones))
    for row in code:
        print("".join(str(b) for b in row))


if __name__ == "__main__":
    main()
