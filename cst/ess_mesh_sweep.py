# -*- coding: utf-8 -*-
"""Build one ESS 10x10 case once, then report the mesh size for several
HexTLM refinement settings (no solve)."""
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

import ess_dataset as E

CODE = [[1, 0, 1, 1, 0],
        [0, 1, 1, 0, 1],
        [1, 1, 0, 1, 1],
        [0, 1, 1, 1, 0],
        [1, 0, 1, 0, 1]]

SETTINGS = [
    ("default (no MeshSettings)", None),
    ("wave30 box60 min0.30 edge2", ("30", "15", "60", "0.30", "1", "2")),
    ("wave40 box80 min0.25 edge2", ("40", "20", "80", "0.25", "1", "2")),
    ("wave30 box60 min0.25 edge2", ("30", "15", "60", "0.25", "1", "2")),
    ("wave20 box40 min0.20 edge2", ("20", "15", "40", "0.20", "1", "2")),
]


def mesh_vba(s):
    if s is None:
        return None
    wnear, wfar, bnear, minstep, edge_on, edge_ratio = s
    return """Sub Main()
    With Mesh
        .MeshType "HexahedralTLM"
    End With
    With MeshSettings
        .SetMeshType "HexTLM"
        .Set "StepsPerWaveNear", "%s"
        .Set "StepsPerWaveFar", "%s"
        .Set "WavelengthRefinementSameAsNear", "0"
        .Set "StepsPerBoxNear", "%s"
        .Set "StepsPerBoxFar", "1"
        .Set "ModelBoxDescrNear", "maxedge"
        .Set "ModelBoxDescrFar", "maxedge"
        .Set "UseRatioLimitGeometry", "0"
        .Set "UseSameMinStepGeometryXYZ", "1"
        .Set "MinStepGeometryX", "%s"
        .Set "MinStepGeometryY", "%s"
        .Set "MinStepGeometryZ", "%s"
        .Set "EdgeRefinementOn", "%s"
        .Set "EdgeRefinementPolicy", "1"
        .Set "EdgeRefinementRatio", "%s"
        .Set "EdgeRefinementBufferLines", "2"
        .Set "RefineEdgeMaterialGlobal", "1"
    End With
End Sub""" % (wnear, wfar, bnear, minstep, minstep, minstep, edge_on, edge_ratio)


def main():
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    de.set_quiet_mode(True)
    prj = de.new_mws()
    time.sleep(0.5)
    m = prj.model3d
    t0 = time.time()
    E.build_case(prj, 10, CODE, 0.35)
    print("built in %.0f s" % (time.time() - t0), flush=True)

    for label, s in SETTINGS:
        vba = mesh_vba(s)
        if vba:
            m._execute_vba_code(vba)
        t1 = time.time()
        try:
            m.add_to_history("mesh", "Mesh.Update", timeout=1800)
            print("%-30s cells %9d | Nx=%4d Ny=%4d Nz=%3d | min %.3f | %.0fs"
                  % (label, m.Mesh.GetNumberOfMeshCells(), m.Mesh.GetNx(), m.Mesh.GetNy(),
                     m.Mesh.GetNz(), m.Mesh.GetActualSmallestHexMeshStep(), time.time() - t1), flush=True)
        except Exception as e:
            print("%-30s FAILED %s" % (label, str(e).replace("\n", " ")[:90]), flush=True)
    prj.close()


if __name__ == "__main__":
    main()
