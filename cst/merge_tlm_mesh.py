# -*- coding: utf-8 -*-
"""Merge the ESS array metal, switch to HexahedralTLM, add local refinement 0.2 mm."""
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

de = cst.interface.DesignEnvironment.connect_to_any()
prj = [p for p in de.get_open_projects()
       if p.filename().lower().endswith("meta_ess_array10.cst")][0]
prj.activate()
m = prj.model3d
print("project:", prj.filename(), "| solver:", m.get_active_solver_name(), flush=True)

metal = [i.split("\\")[-1] for i in m.get_tree_items()
         if i.startswith("Components\\Array\\")
         and i.split("\\")[-1].startswith(("p_", "ring_", "bar_", "metal_"))]
print("metal objects:", len(metal), flush=True)
base = metal[0]
lines = ["Sub Main()"]
for nm in metal[1:]:
    lines.append("    On Error Resume Next")
    lines.append('    Solid.Add "Array:%s", "Array:%s"' % (base, nm))
lines.append("End Sub")
t0 = time.time()
m._execute_vba_code("\n".join(lines))
left = [i for i in m.get_tree_items() if i.startswith("Components\\Array\\")]
print("merged in %.0f s -> %d objects: %s"
      % (time.time() - t0, len(left), [x.split("\\")[-1] for x in left]), flush=True)

for label, code in (
    ("solver TLM", 'ChangeSolverType "TLM"'),
    ("mesh TLM", 'With Mesh\n        .MeshType "HexahedralTLM"\n    End With'),
    ("local refine 0.2",
     'Solid.SetAutomeshStepWidth "Array:%s", 0.2, 0.2, 0.2\n'
     '    Solid.SetMeshExtendwidth "Array:%s", 0.0, 0.0, 0.0' % (base, base)),
):
    try:
        m._execute_vba_code("Sub Main()\n    " + code + "\nEnd Sub")
        print("  [ok] %s" % label, flush=True)
    except Exception as e:
        print("  [fail] %-18s %s" % (label, str(e).replace(chr(10), " ")[:140]), flush=True)

print("solver now:", m.get_active_solver_name(), "| mesh type:", m.Mesh.GetActiveMeshType(), flush=True)

t0 = time.time()
try:
    m.add_to_history("mesh", "Mesh.Update", timeout=3600)
    print("mesh %.0f s | cells %d | Nx=%d Ny=%d Nz=%d"
          % (time.time() - t0, m.Mesh.GetNumberOfMeshCells(),
             m.Mesh.GetNx(), m.Mesh.GetNy(), m.Mesh.GetNz()), flush=True)
except Exception as e:
    print("mesh failed after %.0f s: %s" % (time.time() - t0, str(e).replace(chr(10), " ")[:200]), flush=True)

prj.save(include_results=False, allow_overwrite=True)
print("saved", flush=True)
