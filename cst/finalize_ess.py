# -*- coding: utf-8 -*-
"""Clean ESS-array build: TLM solver, top metal merged per cluster, local 0.2 mm.

TLM is selected via Solver.Method "Hexahedral TLM" (not ChangeSolverType).
Top metal is merged in two kinds of clusters (fast binary-tree merge, no
sequential O(n^2)):
    * the network  = state-0 full sheets + state-1 rings  -> 1 solid
    * per sub-cell = 44 patches + 2 bars (connected)       -> 1 solid each
Then a 0.2 mm local mesh refinement is applied only to the coding-cell clusters
(which span ~15 mm, so it stays LOCAL instead of exploding over 300 mm).
"""
import sys
import time

sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface

import build_ess_array as E


def merge_groups(m, groups):
    """groups: list of lists of object short names.  Merges each group to one solid."""
    for g in groups:
        if len(g) <= 1:
            continue
        lines = ["Sub Main()"]
        cur = g
        while len(cur) > 1:
            nxt = []
            i = 0
            while i < len(cur):
                if i + 1 < len(cur):
                    lines.append("    On Error Resume Next")
                    lines.append('    Solid.Add "Array:%s", "Array:%s"' % (cur[i], cur[i + 1]))
                    nxt.append(cur[i])
                    i += 2
                else:
                    nxt.append(cur[i])
                    i += 1
            cur = nxt
        lines.append("End Sub")
        m._execute_vba_code("\n".join(lines))


def main():
    de = cst.interface.DesignEnvironment.connect_to_any()
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

    blocks, st1, st0 = E.build_blocks()
    print("macro %dx%d | state1 %d state0 %d | array %.0f mm" % (E.MACRO, E.MACRO, st1, st0, E.L), flush=True)

    prj = de.new_mws()
    time.sleep(1.0)
    m = prj.model3d
    t0 = time.time()
    for cap, txt in blocks:
        m.add_to_history(cap, txt, timeout=1800)
    print("built in %.0f s" % (time.time() - t0), flush=True)

    names = [i.split("\\")[-1] for i in m.get_tree_items() if i.startswith("Components\\Array\\")]
    network = [n for n in names if "_ring" in n or "_metal" in n]
    clusters = {}
    for n in names:
        for key in ("_p_", "_bar_"):
            k = n.find(key)
            if k > 0:
                pfx = n[:k]
                clusters.setdefault(pfx, []).append(n)
                break
    print("network objects %d | clusters %d" % (len(network), len(clusters)), flush=True)

    t0 = time.time()
    merge_groups(m, [network] + list(clusters.values()))
    print("merged in %.0f s" % (time.time() - t0), flush=True)

    left = [i.split("\\")[-1] for i in m.get_tree_items() if i.startswith("Components\\Array\\")]
    print("solids now: %d (network + %d clusters + substrate + ground + lumps)"
          % (len(left), len(clusters)), flush=True)

    # local 0.2 mm refinement on the coding-cell clusters only (they start with "c").
    # After the binary merge the survivor of each group keeps the group's first name.
    cluster_survivors = [clusters[pfx][0] for pfx in sorted(clusters)]
    lines = ["Sub Main()"]
    for n in cluster_survivors:
        lines.append('    Solid.SetAutomeshStepWidth "Array:%s", 0.2, 0.2, 0.0' % n)
        lines.append('    Solid.SetMeshExtendwidth "Array:%s", 0.0, 0.0, 0.0' % n)
    lines.append("End Sub")
    if cluster_survivors:
        m._execute_vba_code("\n".join(lines))
        print("local 0.2 mm refinement applied to %d clusters" % len(cluster_survivors), flush=True)

    t0 = time.time()
    m.add_to_history("mesh", "Mesh.Update", timeout=3600)
    print("TLM mesh %.0f s | cells %d | Nx=%d Ny=%d Nz=%d"
          % (time.time() - t0, m.Mesh.GetNumberOfMeshCells(),
             m.Mesh.GetNx(), m.Mesh.GetNy(), m.Mesh.GetNz()), flush=True)

    prj.save(E.OUT, include_results=False, allow_overwrite=True)
    print("saved:", E.OUT, flush=True)


if __name__ == "__main__":
    main()
